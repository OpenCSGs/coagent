import asyncio
import pytest
from typing import Callable, Awaitable, AsyncIterator

from coagent.core.types import Address, RawMessage, Channel, Subscription
from coagent.core.agent import BaseAgent, Context, handler
from coagent.core.messages import Cancel, Message


class TestChannel(Channel):
    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def publish(
        self,
        addr: Address,
        msg: RawMessage,
        request: bool = False,
        reply: str = "",
        timeout: float = 0.5,
        probe: bool = True,
    ) -> RawMessage | None:
        pass

    async def publish_multi(
        self,
        addr: Address,
        msg: RawMessage,
        probe: bool = True,
    ) -> AsyncIterator[RawMessage]:
        pass

    async def subscribe(
        self,
        addr: Address,
        handler: Callable[[RawMessage], Awaitable[None]],
        queue: str = "",
    ) -> Subscription:
        pass

    async def new_reply_topic(self) -> str:
        pass


class Run(Message):
    pass


class BlockingAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.cancelled = False

    @handler
    async def handle(self, msg: Run, ctx: Context) -> None:
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            self.cancelled = True


class TestBlockingAgent:
    @pytest.mark.asyncio
    async def test_receive(self):
        agent = BlockingAgent()
        agent.init(TestChannel(), Address(name="test", id="0"))
        await agent.start()

        await agent.receive(Run().encode())
        await asyncio.sleep(0.001)  # Give the agent a chance to run the handler
        assert agent.cancelled is False

        await agent.receive(Cancel().encode())
        await asyncio.sleep(0.001)  # Give the agent a chance to run the handler
        assert agent.cancelled is True

        await agent.stop()
