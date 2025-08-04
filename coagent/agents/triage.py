import re
from typing import AsyncIterator

from coagent.core import (
    Address,
    BaseAgent,
    Context,
    DiscoveryBatchQuery,
    DiscoveryBatchReply,
    DiscoveryQuery,
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
from .memory import Memory, NoMemory
from .model import default_model, Model


class UpdateSubAgents(Message):
    agents: list[Schema]


class Triage(BaseAgent):
    """A triage agent that delegates conversation to its sub-agents.

    Args:
        name: The name of the agent.
        system: The system instruction for the agent.
        static_agents: A list of static agent names to delegate to.
        dynamic_agents: A list of queries to dynamically discover agents to delegate to.
        model: The model to use for generating responses.
        timeout: The timeout for the agent.
    """

    def __init__(
        self,
        name: str = "",
        system: str = "",
        model: Model = default_model,
        memory: Memory | None = None,
        static_agents: list[str] | None = None,
        dynamic_agents: list[DiscoveryQuery] | None = None,
        timeout: float = 300,
    ):
        super().__init__(timeout=timeout)

        self._name: str = name
        self._system: str = system
        self._static_agents: list[str] | None = static_agents
        self._dynamic_agents: list[DiscoveryQuery] | None = dynamic_agents
        self._model: Model = model

        self._swarm_client = Swarm(self.model)

        self._sub_agents: dict[str, Schema] = {}
        self._swarm_agent: SwarmAgent | None = None

        self._memory: Memory = memory or NoMemory()
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
    def model(self) -> Model:
        return self._model

    @property
    def memory(self) -> Memory:
        return self._memory

    @property
    def static_agents(self) -> list[str] | None:
        return self._static_agents

    @property
    def dynamic_agents(self) -> list[DiscoveryQuery] | None:
        return self._dynamic_agents

    def get_swarm_client(self, extensions: dict) -> Swarm:
        """Get the swarm client with the given message extensions.

        Override this method to customize the swarm client.
        """
        model_id = extensions.get("model_id", "")
        if model_id:
            # We assume that non-empty model ID indicates the use of a dynamic model.
            model = Model(
                id=model_id,
                base_url=extensions.get("model_base_url", ""),
                api_key=extensions.get("model_api_key", ""),
                api_version=extensions.get("model_api_version", ""),
            )
            return Swarm(model)

        return self._swarm_client

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
            model=self.model.id,
            instructions=self.system,
            functions=tools,
        )

    def _transfer_to_agent(self, agent_type: str):
        async def run() -> AsyncIterator[ChatMessage]:
            # TODO: Handle memory?
            async for chunk in Delegate(self, agent_type).handle(self._history):
                yield chunk

        return run

    async def start(self) -> None:
        await super().start()

        all_queries: list[DiscoveryQuery] = []
        if self.dynamic_agents:
            all_queries.extend(self.dynamic_agents)

            # Subscribe to updates for dynamic sub-agents.
            msg = SubscribeToAgentUpdates(
                sender=self.address, queries=self.dynamic_agents
            )
            await self.channel.publish(
                Address(name="discovery"), msg.encode(), probe=False
            )

        if self.static_agents:
            all_queries.extend(
                [
                    # Only query the agent whose name equals to the namespace.
                    #
                    # We assume that, apart from the agent itself, there are
                    # no other sub-agents in this namespace.
                    DiscoveryQuery(namespace=name, inclusive=True)
                    for name in self.static_agents
                ]
            )

        # To make the newly-created triage agent immediately available,
        # we must retrieve its static and dynamic sub-agents once in advance.
        batch_query = DiscoveryBatchQuery(queries=all_queries)
        result: RawMessage = await self.channel.publish(
            Address(name="discovery"),
            batch_query.encode(),
            request=True,
            probe=False,
        )
        batch_reply: DiscoveryBatchReply = DiscoveryBatchReply.decode(result)

        self._sub_agents = {
            agent.name: agent for reply in batch_reply.replies for agent in reply.agents
        }
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
        # TODO: Handle memory?
        response = self._handle_history(msg, ctx)
        async for resp in response:
            yield resp

    @handler
    async def handle_message(
        self, msg: ChatMessage, ctx: Context
    ) -> AsyncIterator[ChatMessage]:
        existing = await self.memory.get_items()
        history = ChatHistory(messages=existing + [msg])

        response = self._handle_history(history, ctx)
        full_content = ""
        async for resp in response:
            yield resp
            full_content += resp.content

        await self.memory.add_items(
            msg,  # input item
            ChatMessage(role="assistant", content=full_content),  # output item
        )

    async def _handle_history(
        self, msg: ChatHistory, ctx: Context
    ) -> AsyncIterator[ChatMessage]:
        # For now, we assume that the agent is processing messages sequentially.
        self._history: ChatHistory = msg

        swarm_client = self.get_swarm_client(msg.extensions)
        response = swarm_client.run_and_stream(
            agent=self._swarm_agent,
            messages=[m.model_dump() for m in msg.messages],
            context_variables=msg.extensions,
        )
        async for resp in response:
            if isinstance(resp, ChatMessage) and resp.content:
                yield resp
