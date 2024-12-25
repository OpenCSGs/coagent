import asyncio

from coagent.agents import ChatAgent
from coagent.core import idle_loop, new, set_stderr_logger
from coagent.runtimes import NATSRuntime


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(
            "translator",
            new(
                ChatAgent,
                system="""You are a professional translator that can translate Chinese to English.""",
            ),
        )
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger("TRACE")

    asyncio.run(main())
