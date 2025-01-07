import asyncio

from coagent.agents import StreamChatAgent
from coagent.core import AgentSpec, idle_loop, new, set_stderr_logger
from coagent.runtimes import NATSRuntime


translator = AgentSpec(
    "translator",
    new(
        StreamChatAgent,
        system="""You are a professional translator that can translate Chinese to English.""",
    ),
)


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(translator)
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger("TRACE")

    asyncio.run(main())
