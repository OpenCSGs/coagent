import asyncio
import functools
import inspect

import pytest

from coagent.core.types import Agent
from coagent.core.util import wait_for_shutdown
from coagent.core.runtime import NopChannel
from coagent.runtimes.local_runtime import LocalChannel


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
        await wait_for_shutdown()
        await agent.stop()

    return asyncio.create_task(run())


@pytest.fixture
@helper_func
async def yield_control():
    """A fixture to yield control to other coroutines."""
    await asyncio.sleep(0.000001)
