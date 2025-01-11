import asyncio

import pytest

from coagent.core.types import Address
from coagent.core.agent import BaseAgent, Context, handler
from coagent.core.messages import Cancel, Message


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
    async def test_receive(self, test_channel):
        agent = BlockingAgent()
        agent.init(test_channel, Address(name="test", id="0"))
        await agent.start()

        await agent.receive(Run().encode())
        await asyncio.sleep(0.001)  # Give the agent a chance to run the handler
        assert agent.cancelled is False

        await agent.receive(Cancel().encode())
        await asyncio.sleep(0.001)  # Give the agent a chance to run the handler
        assert agent.cancelled is True

        await agent.stop()
