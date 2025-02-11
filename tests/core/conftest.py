import asyncio
import functools
import inspect
from typing import Callable, Awaitable

import pytest

from coagent.core.types import Address, Agent, RawMessage, Channel, Subscription
from coagent.core.util import idle_loop
from coagent.runtimes.local_runtime import LocalChannel


class NopChannel(Channel):
    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def publish(
        self,
        addr: Address,
        msg: RawMessage,
        stream: bool = False,
        request: bool = False,
        reply: str = "",
        timeout: float = 0.5,
        probe: bool = True,
    ) -> RawMessage | None:
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


@pytest.fixture
def nop_channel() -> NopChannel:
    return NopChannel()


@pytest.fixture
def local_channel() -> LocalChannel:
    return LocalChannel()


def helper_func(func):
    """A decorator to create a fixture that returns the wrapped function."""

    def wrapper():
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def run(*args, **kwargs):
                return await func(*args, **kwargs)
        else:

            @functools.wraps(func)
            def run(*args, **kwargs):
                return func(*args, **kwargs)

        return run

    return wrapper


@pytest.fixture
@helper_func
def run_agent_in_task(agent: Agent) -> asyncio.Task:
    """Run the given agent in a task."""

    async def run():
        await agent.start()
        await idle_loop()
        await agent.stop()

    return asyncio.create_task(run())


@pytest.fixture
@helper_func
async def yield_control():
    """A fixture to yield control to other coroutines."""
    await asyncio.sleep(0.000001)
