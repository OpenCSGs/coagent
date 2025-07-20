import asyncio

from coagent.agents import ChatAgent
from coagent.agents.mcp_server import MCPServer, NamedMCPServer
from coagent.core import AgentSpec, new, init_logger
from coagent.runtimes import NATSRuntime


# The agent for managing MCP servers
server = AgentSpec("mcp_server", new(MCPServer))

agent = AgentSpec(
    "mcp",
    new(
        ChatAgent,
        mcp_servers=[NamedMCPServer(name="server1")],
        system="You are a helpful Weather Reporter",
    ),
)


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(server)
        await runtime.register(agent)
        await runtime.wait_for_shutdown()


if __name__ == "__main__":
    init_logger("TRACE")
    asyncio.run(main())
