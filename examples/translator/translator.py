import asyncio

from coagent.agents import ChatAgent
from coagent.core import AgentSpec, idle_loop, new, init_logger
from coagent.runtimes import NATSRuntime


translator = AgentSpec(
    "translator",
    new(
        ChatAgent,
        system="""You are a professional translator that can translate Chinese to English.""",
    ),
)


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(translator)
        await idle_loop()


if __name__ == "__main__":
    init_logger("TRACE")

    asyncio.run(main())
