import asyncio

from coagent.agents import ChatAgent
from coagent.agents.mcp_server import MCPServer
from coagent.core import AgentSpec, idle_loop, new, set_stderr_logger
from coagent.runtimes import NATSRuntime


server = AgentSpec("mcp_server", new(MCPServer))

agent = AgentSpec(
    "mcp",
    new(
        ChatAgent,
        mcp_servers=["server1"],
        system="You are a helpful Weather Reporter",
    ),
)


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(server)
        await runtime.register(agent)
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger("TRACE")
    asyncio.run(main())
