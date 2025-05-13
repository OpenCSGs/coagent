import asyncio

from coagent.agents import ChatAgent, ChatMessage
from coagent.agents.mcp_server import MCPServer, MCPServerStdioParams, Connect, Close
from coagent.core import AgentSpec, new, set_stderr_logger, logger
from coagent.runtimes import LocalRuntime


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
    async with LocalRuntime() as runtime:
        await runtime.register(server)
        await runtime.register(agent)

        logger.info("Connecting to the server")
        await server.run(
            Connect(
                transport="stdio",
                params=MCPServerStdioParams(
                    command="python",
                    args=["examples/mcp-new/server.py"],
                ),
            ).encode(),
            session_id="server1",
        )

        logger.info("Chatting with the agent")
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

        logger.info("Close the server")
        await server.run(
            Close().encode(),
            session_id="server1",
            request=False,
        )


if __name__ == "__main__":
    set_stderr_logger()
    asyncio.run(main())
