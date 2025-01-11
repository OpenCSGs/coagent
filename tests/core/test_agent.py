import asyncio
from typing import AsyncIterator

import pytest

from coagent.core.types import Address
from coagent.core.agent import BaseAgent, Context, handler
from coagent.core.exceptions import BaseError
from coagent.core.messages import Cancel, Message


class Query(Message):
    pass


class Reply(Message):
    pass


class TrivialAgent(BaseAgent):
    def __init__(self, wait_s: float = 0) -> None:
        super().__init__()
        self.wait_s = wait_s

    @handler
    async def handle(self, msg: Query, ctx: Context) -> Reply:
        if self.wait_s > 0:
            await asyncio.sleep(self.wait_s)
        return Reply()


class StreamAgent(BaseAgent):
    def __init__(self, chunk_size: int = 1, wait_s: float = 0) -> None:
        super().__init__()
        self.chunk_size = chunk_size
        self.wait_s = wait_s

    @handler
    async def handle(self, msg: Query, ctx: Context) -> AsyncIterator[Reply]:
        for _ in range(self.chunk_size):
            if self.wait_s > 0:
                await asyncio.sleep(self.wait_s)
            yield Reply()


class TestTrivialAgent:
    @pytest.mark.asyncio
    async def test_normal(self, local_channel, run_agent_in_task, yield_control):
        agent = TrivialAgent()
        addr = Address(name="test", id="0")
        agent.init(local_channel, addr)

        _task = run_agent_in_task(agent)
        await yield_control()

        result = await local_channel.publish(
            addr, Query().encode(), request=True, probe=False
        )
        assert result.header.type == "Reply"

    @pytest.mark.asyncio
    async def test_cancel(self, local_channel, run_agent_in_task, yield_control):
        agent = TrivialAgent(wait_s=10)
        addr = Address(name="test", id="1")
        agent.init(local_channel, addr)

        _task = run_agent_in_task(agent)
        await yield_control()

        async def cancel():
            await asyncio.sleep(0.01)
            await local_channel.publish(addr, Cancel().encode())

        _ = asyncio.create_task(cancel())
        await yield_control()

        with pytest.raises(BaseError) as exc:
            await local_channel.publish(
                addr, Query().encode(), request=True, probe=False
            )
        assert str(exc.value).endswith("asyncio.exceptions.CancelledError\n")


class TestStreamAgent:
    @pytest.mark.asyncio
    async def test_normal(self, local_channel, run_agent_in_task, yield_control):
        agent = StreamAgent()
        addr = Address(name="test", id="2")
        agent.init(local_channel, addr)

        _task = run_agent_in_task(agent)
        await yield_control()

        result = local_channel.publish_multi(addr, Query().encode(), probe=False)
        async for chunk in result:
            assert chunk.header.type == "Reply"

    @pytest.mark.asyncio
    async def test_cancel(self, local_channel, run_agent_in_task, yield_control):
        agent = StreamAgent(wait_s=10)
        addr = Address(name="test", id="3")
        agent.init(local_channel, addr)

        _task = run_agent_in_task(agent)
        await yield_control()

        async def cancel():
            await asyncio.sleep(0.01)
            await local_channel.publish(addr, Cancel().encode())

        _ = asyncio.create_task(cancel())
        await yield_control()

        result = local_channel.publish_multi(addr, Query().encode(), probe=False)
        with pytest.raises(BaseError) as exc:
            async for _chunk in result:
                pass
        assert str(exc.value).endswith("asyncio.exceptions.CancelledError\n")
