from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from .agent import BaseAgent, Context, handler, Operation
from .messages import Message
from .types import (
    Address,
    Constructor,
    RawMessage,
)
from .util import Trie


SEPARATOR = "."


class Schema(BaseModel):
    """A schema of an agent."""

    name: str
    description: str = ""
    operations: list[Operation] = []

    def __lt__(self, other: Schema):
        # Sort by name
        return self.name < other.name


class DiscoveryQuery(Message):
    """A message to discover agents in a namespace."""

    namespace: str = Field(..., description="The namespace to discover agents in.")
    recursive: bool = Field(
        default=False,
        description="Whether to recursively discover agents in sub-namespaces.",
    )
    inclusive: bool = Field(
        default=False,
        description="Whether to include the agent whose name equals to the query namespace.",
    )
    detailed: bool = Field(
        default=False,
        description="Whether to return detailed operations for each agent.",
    )

    def matches(self, name: str) -> bool:
        """Check if the given name (agent type) matches the query."""

        if not name:
            # name is empty.
            return False

        if not name.startswith(self.namespace):
            # name is not under the namespace.
            return False

        if name == self.namespace:
            return self.inclusive

        name_level = len(name.split(SEPARATOR))
        namespace_level = len(self.namespace.split(SEPARATOR)) if self.namespace else 0
        if name_level == namespace_level + 1:
            return True

        # grandchild or great-grandchild, etc.
        return self.recursive


class DiscoveryReply(Message):
    """A reply message to a discover message."""

    agents: list[Schema]


class SubscribeToAgentUpdates(Message):
    """A message to subscribe to updates on the registration and deregistration
    of agents that match the given query.
    """

    sender: Address = Field(
        ..., description="The address of the agent initiating the subscription."
    )
    query: DiscoveryQuery


class UnsubscribeFromAgentUpdates(Message):
    """A message to unsubscribe from updates on the registration and deregistration
    of agents.
    """

    sender: Address = Field(
        ..., description="The address of the agent initiating the unsubscription."
    )


class AgentsRegistered(Message):
    """A message to notify that one or more agents have been registered."""

    agents: list[Schema] = Field(description="A list of agent schemas.")


class AgentsDeregistered(Message):
    """A message to notify that one or more agents have been deregistered."""

    agents: list[Schema] = Field(description="A list of agent schemas.")


class Discovery(BaseAgent):
    """A discovery agent that can discover agents in given namespaces.

    Internally, the agent acts as an aggregator. Upon receiving a discovery
    request, it will initiate a query to all discovery servers, and then
    aggregate the replies from these servers.
    """

    def __init__(self):
        super().__init__()

        # The local discovery server.
        self._server: DiscoveryServer | None = None

    async def start(self) -> None:
        """Since discovery is a special agent, we need to start it in a different way."""

        # Each query message can only be received and handled by one discovery aggregator.
        self._sub = await self.channel.subscribe(
            self.address,
            handler=self.receive,
            queue=f"{self.address.topic}_workers",
        )

        # Create and start the local discovery server.
        self._server = DiscoveryServer()
        # We MUST set the channel and address manually.
        self._server.init(self.channel, Address(name=f"{self.address.name}.server"))
        await self._server.start()

    async def stop(self) -> None:
        """Since discovery is a special agent, we need to stop it in a different way."""
        if self._server:
            await self._server.stop()

        if self._sub:
            await self._sub.unsubscribe()

    async def register(
        self, name: str, constructor: Constructor, description: str = ""
    ) -> None:
        if name == self.address.name:
            raise ValueError(f"Agent type '{self.address.name}' is reserved")

        if self._server:
            await self._server.register(name, constructor, description)

    async def deregister(self, *names: str) -> None:
        if self._server:
            await self._server.deregister(*names)

    @handler
    async def discover(self, msg: DiscoveryQuery, ctx: Context) -> DiscoveryReply:
        """Discover agents in a given namespace in a distributed manner."""
        lock: asyncio.Lock = asyncio.Lock()
        agents: dict[str, Schema] = {}

        # TODO: Use QueueSubscriptionIterator to simplify this.
        async def receive(raw: RawMessage) -> None:
            # Gather
            reply = DiscoveryReply.decode(raw)
            if not reply.agents:
                return

            await lock.acquire()
            try:
                for agent in reply.agents:
                    agents[agent.name] = agent
            finally:
                lock.release()

        inbox = await self.channel.new_reply_topic()
        sub = await self.channel.subscribe(addr=Address(name=inbox), handler=receive)

        try:
            # Scatter
            await self.channel.publish(
                self._server.address,
                msg.encode(),
                request=True,
                reply=inbox,
                probe=False,
            )

            # Wait for all discovery servers to respond or timed out.
            # FIXME: How to get the original timeout specified by the publisher?
            await asyncio.sleep(0.45)  # Smaller than the default timeout (0.5s).

        finally:
            await sub.unsubscribe()

            sorted_agents = sorted(agents.values())
            return DiscoveryReply(agents=sorted_agents)

    @handler
    async def subscribe_to_agent_updates(
        self, msg: SubscribeToAgentUpdates, ctx: Context
    ) -> None:
        """Subscribe to updates on the registration and deregistration
        of agents that match the given query.
        """

        # Simply broadcast the message to all discovery servers.
        await self.channel.publish(self._server.address, msg.encode(), probe=False)

    @handler
    async def unsubscribe_from_agent_updates(
        self, msg: UnsubscribeFromAgentUpdates, ctx: Context
    ) -> None:
        """Unsubscribe from updates on the registration and deregistration
        of agents.
        """

        # Simply broadcast the message to all discovery servers.
        await self.channel.publish(self._server.address, msg.encode(), probe=False)


class _SynchronizeQuery(Message):
    """An internal message to synchronize agent-subscriptions from other discovery servers."""


class _SynchronizeReply(Message):
    """An internal reply message to a synchronize message."""

    subscriptions: dict[str, DiscoveryQuery] = Field(description="Agent subscriptions.")


class DiscoveryServer(BaseAgent):
    """A discovery server.

    When receiving a discovery query from the discovery aggregator, it will
    search locally for agents under the given namespace and return them to
    the discovery aggregator.
    """

    def __init__(self):
        super().__init__()

        self._agent_schemas: Trie = Trie(separator=SEPARATOR)
        self._agent_subscriptions: dict[Address, DiscoveryQuery] = {}

    async def start(self) -> None:
        """Since discovery server is a special agent, we need to start it in a different way."""

        # Upon startup, the current discovery server has no agent-subscriptions.
        # Therefore, it's necessary to synchronize the existing agent-subscriptions
        # from other discovery servers.
        #
        # Note that to avoid receiving the _SynchronizeQuery message sent by
        # itself, the discovery server synchronizes with other discovery servers
        # before subscribing to its own address.

        async def receive(raw: RawMessage) -> None:
            # Gather
            reply = _SynchronizeReply.decode(raw)
            for topic, query in reply.subscriptions.items():
                addr = Address.from_topic(topic)
                self._agent_subscriptions[addr] = query

        inbox = await self.channel.new_reply_topic()
        sub = await self.channel.subscribe(addr=Address(name=inbox), handler=receive)

        try:
            # Scatter
            await self.channel.publish(
                self.address,
                _SynchronizeQuery().encode(),
                request=True,
                reply=inbox,
                probe=False,
            )

            # Wait for all discovery servers to respond or timed out.
            await asyncio.sleep(0.2)  # TODO: Choose a better timeout.
        finally:
            await sub.unsubscribe()

        # Subscribe the agent to its own address.
        self._sub = await self.channel.subscribe(self.address, handler=self.receive)

    async def stop(self) -> None:
        """Since discovery server is a special agent, we need to stop it in a different way."""

        # Unsubscribe the agent from its own address.
        if self._sub:
            await self._sub.unsubscribe()

    async def register(
        self, name: str, constructor: Constructor, description: str = ""
    ) -> None:
        if name == self.address.name:
            raise ValueError(f"Agent type '{self.address.name}' is reserved")
        if name in self._agent_schemas:
            raise ValueError(f"Agent type '{name}' already registered")

        operations = constructor.type.collect_operations()
        description = description or constructor.type.__doc__ or ""
        schema = Schema(name=name, description=description, operations=operations)
        self._agent_schemas[name] = schema

        # Notify all subscribers about the registration of the new agent.
        for addr, query in self._agent_subscriptions.items():
            if query.matches(name):
                msg = AgentsRegistered(
                    agents=[Schema(name=schema.name, description=schema.description)]
                )
                await self.channel.publish(addr, msg.encode())

    async def deregister(self, *names: str) -> None:
        candidate_names = []

        if names:
            for name in names:
                schema = self._agent_schemas.pop(name, None)
                if schema:
                    candidate_names.append(name)
        else:
            candidate_names = self._agent_schemas.keys()
            self._agent_schemas.clear()

        # Notify all subscribers about the deregistration of the involved agents.
        for addr, query in self._agent_subscriptions.items():
            matched_names = [name for name in candidate_names if query.matches(name)]
            if matched_names:
                msg = AgentsDeregistered(
                    agents=[Schema(name=name) for name in matched_names]
                )
                await self.channel.publish(addr, msg.encode())

    @handler
    async def synchronize(
        self, msg: _SynchronizeQuery, ctx: Context
    ) -> _SynchronizeReply:
        subscriptions = {
            addr.topic: query for addr, query in self._agent_subscriptions.items()
        }
        return _SynchronizeReply(subscriptions=subscriptions)

    @handler
    async def search(self, msg: DiscoveryQuery, ctx: Context) -> DiscoveryReply:
        """
        Examples:

        given agents:
            a
            a.x
            a.x.0
            a.y
            a.y.0
            b
            b.x
            b.y
            b.z.0

        namespace="", recursive=False:
            a
            b

        namespace="", recursive=True:
            a
            a.x
            a.x.0
            a.y
            a.y.0
            b
            b.x
            b.y
            b.z.0

        namespace="a", recursive=False:
            a
            a.x
            a.y

        namespace="a", recursive=True:
            a
            a.x
            a.x.0
            a.y
            a.y.0

        namespace="b", recursive=False:
            b
            b.x
            b.y

        namespace="b", recursive=True:
            b
            b.x
            b.y
            b.z.0
        """
        if msg.recursive:
            try:
                namespace = msg.namespace or Trie.EMPTY
                schemas = self._agent_schemas.values(namespace)
            except KeyError:
                schemas = []
        else:
            schemas = self._agent_schemas.direct_values(msg.namespace)

        def filter_agent(schema: Schema) -> bool:
            if not schema:
                return False
            if not msg.inclusive:
                return schema.name != msg.namespace
            return True

        agents = [
            Schema(
                name=schema.name,
                description=schema.description,
                operations=schema.operations if msg.detailed else [],
            )
            for schema in schemas
            if filter_agent(schema)
        ]
        return DiscoveryReply(agents=agents)

    @handler
    async def subscribe_to_agent_updates(
        self, msg: SubscribeToAgentUpdates, ctx: Context
    ) -> None:
        self._agent_subscriptions[msg.sender] = msg.query

    @handler
    async def unsubscribe_from_agent_updates(
        self, msg: UnsubscribeFromAgentUpdates, ctx: Context
    ) -> None:
        self._agent_subscriptions.pop(msg.sender, None)