import asyncio

from coagent.agents import Sequential
from coagent.core import AgentSpec, new, init_logger
from coagent.runtimes import NATSRuntime


team = AgentSpec("team", new(Sequential, "dev", "qa"))


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(team)
        await runtime.wait_for_shutdown()


if __name__ == "__main__":
    init_logger("TRACE")

    asyncio.run(main())
