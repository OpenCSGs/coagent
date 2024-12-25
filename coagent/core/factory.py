import asyncio

from .agent import BaseAgent, Context, handler
from .logger import logger
from .messages import Message
from .types import (
    Address,
    Agent,
    Constructor,
    State,
)


class CreateAgent(Message):
    """A message to create an agent associated with a session ID."""

    session_id: str


class DeleteAgent(Message):
    """A message to delete an agent associated with a session ID."""

    session_id: str


class Factory(BaseAgent):
    """A factory is a special agent that manages one type of primitive agents.

    Therefore, it is a singleton agent for each type of primitive agents and
    its address is corresponding with the name of the agent type.
    """

    def __init__(self, name: str, constructor: Constructor):
        super().__init__()

        self._name: str = name
        self._constructor: Constructor = constructor

        self._agents: dict[Address, Agent] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

        self._recycle_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Since factory is a special agent, we need to start it in a different way."""
        # Subscribe the factory to the given address.
        #
        # Note that we specify a queue parameter to distribute requests among
        # multiple factory agents of the same type of primitive agent.
        self._sub = await self.channel.subscribe(
            self.address,
            handler=self.receive,
            queue=f"{self.address.topic}_workers",
        )

        # Start the recycle loop.
        self._recycle_task = asyncio.create_task(self._recycle())

    async def stop(self) -> None:
        """Since factory is a special agent, we need to stop it in a different way."""
        # Unsubscribe the factory from the address.
        if self._sub:
            await self._sub.unsubscribe()

        # Stop all agents.
        for agent in self._agents.values():
            await agent.stop()
        self._agents.clear()

        # Cancel the recycle loop.
        if self._recycle_task:
            self._recycle_task.cancel()

    async def _recycle(self) -> None:
        """The recycle loop for deleting idle agents."""
        while True:
            # Recycle every 20 seconds.
            # TODO: Make the recycle interval configurable.
            await asyncio.sleep(20)

            total_num: int = 0
            idle_agents: list[Address] = []

            async with self._lock:
                for addr, agent in self._agents.items():
                    total_num += 1
                    state = await agent.get_state()
                    if state == State.IDLE:
                        idle_agents.append(addr)

            idle_num = len(idle_agents)
            if not idle_num:
                continue

            running_num = total_num - idle_num
            logger.debug(
                f"[Factory {self.address.name}] Recycling agents: {running_num} running, {idle_num} idle"
            )

            deleted_agents: list[Agent] = []
            async with self._lock:
                for addr in idle_agents:
                    agent = self._agents.pop(addr, None)
                    if agent:
                        deleted_agents.append(agent)

            for agent in deleted_agents:
                await agent.stop()

    @handler
    async def create_agent(self, msg: CreateAgent, ctx: Context) -> None:
        async with self._lock:
            addr = Address(name=self._name, id=msg.session_id)
            if addr in self._agents:
                return

            # Create an agent with the given channel and address.
            agent = await self._constructor(self.channel, addr)
            self._agents[addr] = agent

            await agent.start()

    @handler
    async def delete_agent(self, msg: DeleteAgent, ctx: Context) -> None:
        # FIXME: The DeleteAgent will not always be received by the right
        #        factory agent since there are multiple factories working
        #        in load balancing mode.
        async with self._lock:
            addr = Address(name=self._name, id=msg.session_id)
            agent = self._agents.pop(addr, None)
            if agent:
                await agent.stop()
