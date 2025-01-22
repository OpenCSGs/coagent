import re
from typing import AsyncIterator

from coagent.core import (
    Address,
    BaseAgent,
    Context,
    DiscoveryQuery,
    DiscoveryReply,
    handler,
    logger,
    Message,
    RawMessage,
)
from coagent.core.discovery import (
    AgentsRegistered,
    AgentsDeregistered,
    Schema,
    SubscribeToAgentUpdates,
    UnsubscribeFromAgentUpdates,
)

from .aswarm import Agent as SwarmAgent, Swarm
from .chat_agent import ChatHistory, ChatMessage, Delegate
from .model_client import default_model_client, ModelClient


class UpdateSubAgents(Message):
    agents: list[Schema]


class DynamicTriage(BaseAgent):
    """A triage agent that dynamically discovers its sub-agents and delegates conversation to these sub-agents."""

    def __init__(
        self,
        name: str = "",
        system: str = "",
        namespace: str = "",
        inclusive: bool = False,
        client: ModelClient = default_model_client,
    ):
        super().__init__()

        self._name: str = name
        self._system: str = system
        self._namespace: str = namespace
        self._inclusive: bool = inclusive
        self._client: ModelClient = client

        self._swarm_client = Swarm(self.client)

        self._sub_agents: dict[str, Schema] = {}
        self._swarm_agent: SwarmAgent | None = None

        self._history: ChatHistory = ChatHistory(messages=[])

    @property
    def name(self) -> str:
        if self._name:
            return self._name

        n = self.__class__.__name__
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", n).lower()

    @property
    def system(self) -> str:
        """The system instruction for this agent."""
        return self._system

    @property
    def namespace(self) -> str:
        """The namespace for this agent."""
        return self._namespace

    @property
    def inclusive(self) -> bool:
        """Whether to include the agent whose name equals to the namespace."""
        return self._inclusive

    @property
    def client(self) -> ModelClient:
        return self._client

    async def _update_swarm_agent(self) -> None:
        agent_names = list(self._sub_agents.keys())
        logger.debug(
            f"[{self.__class__.__name__} {self.id}] Discovered sub-agents: {agent_names}"
        )

        tools = []
        for agent in self._sub_agents.values():
            transfer_to = self._transfer_to_agent(agent.name)
            transfer_to.__name__ = f"transfer_to_{agent.name.replace('.', '_')}"
            transfer_to.__doc__ = agent.description
            tools.append(transfer_to)

        self._swarm_agent = SwarmAgent(
            name=self.name,
            model=self.client.model,
            instructions=self.system,
            functions=tools,
        )

    def _transfer_to_agent(self, agent_type: str):
        async def run() -> AsyncIterator[ChatMessage]:
            async for chunk in Delegate(self, agent_type).handle(self._history):
                yield chunk

        return run

    async def start(self) -> None:
        await super().start()

        query = DiscoveryQuery(
            namespace=self.namespace,
            inclusive=self.inclusive,
        )
        msg = SubscribeToAgentUpdates(sender=self.address, query=query)
        await self.channel.publish(Address(name="discovery"), msg.encode(), probe=False)

        # To make the newly-created triage agent immediately available,
        # we must query its sub-agents once in advance.
        result: RawMessage = await self.channel.publish(
            Address(name="discovery"),
            query.encode(),
            request=True,
            probe=False,
        )
        reply: DiscoveryReply = DiscoveryReply.decode(result)

        self._sub_agents = {agent.name: agent for agent in reply.agents}
        await self._update_swarm_agent()

    async def stop(self) -> None:
        msg = UnsubscribeFromAgentUpdates(sender=self.address)
        await self.channel.publish(Address(name="discovery"), msg.encode(), probe=False)

        await super().stop()

    @handler
    async def register_sub_agents(self, msg: AgentsRegistered, ctx: Context) -> None:
        for agent in msg.agents:
            self._sub_agents[agent.name] = agent
        await self._update_swarm_agent()

    @handler
    async def deregister_sub_agents(
        self, msg: AgentsDeregistered, ctx: Context
    ) -> None:
        for agent in msg.agents:
            self._sub_agents.pop(agent.name, None)
        await self._update_swarm_agent()

    @handler
    async def handle_history(
        self, msg: ChatHistory, ctx: Context
    ) -> AsyncIterator[ChatMessage]:
        response = self._handle_history(msg, ctx)
        async for resp in response:
            yield resp

    @handler
    async def handle_message(
        self, msg: ChatMessage, ctx: Context
    ) -> AsyncIterator[ChatMessage]:
        history = ChatHistory(messages=[msg])
        response = self._handle_history(history, ctx)
        async for resp in response:
            yield resp

    async def _handle_history(
        self, msg: ChatHistory, ctx: Context
    ) -> AsyncIterator[ChatMessage]:
        # For now, we assume that the agent is processing messages sequentially.
        self._history: ChatHistory = msg

        response = self._swarm_client.run_and_stream(
            agent=self._swarm_agent,
            messages=[m.model_dump() for m in msg.messages],
            context_variables=msg.extensions,
        )
        async for resp in response:
            if isinstance(resp, ChatMessage) and resp.content:
                yield resp
