import sys

import pytest

from coagent.agents.mcp_agent import MCPAgent


class TestMCPAgent:
    @pytest.mark.skipif(sys.platform == "win32", reason="Does not run on Windows.")
    @pytest.mark.asyncio
    async def test_get_tools(self):
        agent = MCPAgent(mcp_server_base_url="python tests/agents/mcp_server.py")
        await agent.started()

        tools = await agent._get_tools()
        tool = tools[0]

        assert tool.__name__ == "query_weather"
        assert tool.__doc__ == "Query the weather in the given city."
        assert tool.__mcp_tool_schema__ == {
            "description": "Query the weather in the given city.",
            "name": "query_weather",
            "parameters": {
                "properties": {
                    "city": {
                        "title": "City",
                        "type": "string",
                    }
                },
                "required": ["city"],
                "title": "query_weatherArguments",
                "type": "object",
            },
        }
        assert tool.__mcp_tool_args__ == ("city",)

        result = await tool(city="Beijing")
        assert result == "The weather in Beijing is sunny."

        await agent.stopped()
