import asyncio

from coagent.agents import MCPAgent
from coagent.agents.mcp_agent import Prompt
from coagent.core import AgentSpec, idle_loop, new, set_stderr_logger
from coagent.runtimes import NATSRuntime


mcp = AgentSpec(
    "mcp",
    new(
        MCPAgent,
        system=Prompt(name="system_prompt", arguments={"role": "Weather Reporter"}),
        mcp_server_base_url="http://localhost:8080",
    ),
)


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(mcp)
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger("TRACE")
    asyncio.run(main())
