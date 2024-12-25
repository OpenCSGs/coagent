import asyncio

from coagent.agents import Sequential
from coagent.core import new, set_stderr_logger
from coagent.core.util import idle_loop
from coagent.runtimes import NATSRuntime


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register("team", new(Sequential, "dev", "qa"))
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger("TRACE")

    asyncio.run(main())
