import asyncio

from coagent.core.messages import (
    Message,
    GenericMessage,
)
from coagent.core.types import Address, RawMessage
from coagent.core.agent import BaseAgent, Context, handler
from coagent.core.util import clear_queue


class AgentCreated(Message):
    """A message to notify an agent is created."""

    addr: Address


class AgentDeleted(Message):
    """A message to notify an agent is deleted."""

    addr: Address


class AgentStarted(Message):
    """A message to notify an agent that it's started."""

    addr: Address


class AgentStopped(Message):
    """A message to notify an agent that it's stopped."""

    addr: Address


class RemoteAgent(BaseAgent):
    """An agent that operates remotely."""

    def __init__(self):
        super().__init__()

        self.queue: asyncio.Queue[RawMessage] = asyncio.Queue()

    async def stop(self) -> None:
        await super().stop()
        await clear_queue(self.queue)

    async def started(self) -> None:
        """This handler is called after the agent is started."""
        msg = AgentStarted(addr=self.address)
        await self.queue.put(msg.encode())

    async def stopped(self) -> None:
        """This handler is called after the agent is stopped."""
        msg = AgentStopped(addr=self.address)
        await self.queue.put(msg.encode())

    async def _handle_data_custom(self, msg: Message, ctx: Context) -> None:
        """Override the default handler to put the message into the queue."""
        await self.queue.put(msg.encode())

    @handler
    async def handle(self, msg: GenericMessage, ctx: Context) -> None:
        """Pretend to be able to handle any messages to ensure that no
        MessageDecodeError will occur in `BaseAgent.receive()`.
        """
        pass
