import asyncio

from coagent.agents import ChatAgent, ChatMessage
from coagent.agents.mcp_server import (
    Connect,
    MCPServer,
    MCPServerStdioParams,
    NamedMCPServer,
)
from coagent.core import AgentSpec, new, set_stderr_logger
from coagent.runtimes import LocalRuntime


# The agent for managing MCP servers
server = AgentSpec("mcp_server", new(MCPServer))

agent = AgentSpec(
    "mcp",
    new(
        ChatAgent,
        mcp_servers=[
            NamedMCPServer(
                name="server1",
                connect=Connect(
                    transport="stdio",
                    params=MCPServerStdioParams(
                        command="python",
                        args=["examples/mcp-new/server.py"],
                    ),
                ),
            ),
        ],
        mcp_server_agent_type=server.name,
        system="You are a helpful Weather Reporter",
    ),
)


async def main():
    async with LocalRuntime() as runtime:
        await runtime.register(server)
        await runtime.register(agent)

        result = await agent.run(
            ChatMessage(
                role="user",
                content="What is the weather like in Beijing",
            ).encode(),
            stream=True,
        )
        async for chunk in result:
            msg = ChatMessage.decode(chunk)
            print(msg.content, end="", flush=True)


if __name__ == "__main__":
    set_stderr_logger("DEBUG")
    asyncio.run(main())
