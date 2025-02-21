import sys

import pytest

from coagent.agents.mcp_agent import MCPAgent, Prompt
from coagent.core.exceptions import BaseError


class TestMCPAgent:
    @pytest.mark.skipif(sys.platform == "win32", reason="Does not run on Windows.")
    @pytest.mark.asyncio
    async def test_get_prompt(self):
        agent = MCPAgent(mcp_server_base_url="python tests/agents/mcp_server.py")
        await agent.started()

        # String
        config = "You are a helpful Weather Reporter."
        prompt = await agent._get_prompt(config)
        assert prompt == "You are a helpful Weather Reporter."

        # Prompt
        config = Prompt(name="system_prompt", arguments={"role": "Weather Reporter"})
        prompt = await agent._get_prompt(config)
        assert prompt == "You are a helpful Weather Reporter."

        # Error
        config = Prompt(name="x", arguments={"role": "Weather Reporter"})
        with pytest.raises(BaseError) as exc:
            _ = await agent._get_prompt(config)
        assert str(exc.value).startswith("Unknown prompt: x")

        await agent.stopped()

    @pytest.mark.skipif(sys.platform == "win32", reason="Does not run on Windows.")
    @pytest.mark.asyncio
    async def test_get_tools(self):
        agent = MCPAgent(mcp_server_base_url="python tests/agents/mcp_server.py")
        await agent.started()

        tools = await agent._get_tools()
        assert len(tools) == 2

        # Get query_weather
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

        # Call query_weather
        result = await tool(city="Beijing")
        assert result == "The weather in Beijing is sunny."

        # Get book_flight
        tool = tools[1]
        assert tool.__name__ == "book_flight"
        assert tool.__doc__ == "Book a flight from departure to arrival."
        assert tool.__mcp_tool_schema__ == {
            "description": "Book a flight from departure to arrival.",
            "name": "book_flight",
            "parameters": {
                "properties": {
                    "arrival": {
                        "title": "Arrival",
                        "type": "string",
                    },
                    "departure": {
                        "title": "Departure",
                        "type": "string",
                    },
                },
                "required": ["departure", "arrival"],
                "title": "book_flightArguments",
                "type": "object",
            },
        }
        assert tool.__mcp_tool_args__ == ("departure", "arrival")

        # Call book_flight
        result = await tool(departure="Beijing", arrival="Shanghai")
        assert result == "Flight from Beijing to Shanghai has been booked."

        await agent.stopped()

    @pytest.mark.skipif(sys.platform == "win32", reason="Does not run on Windows.")
    @pytest.mark.asyncio
    async def test_get_tools_with_selection(self):
        agent = MCPAgent(
            mcp_server_base_url="python tests/agents/mcp_server.py",
            selected_tools=["query_weather"],
        )
        await agent.started()

        tools = await agent._get_tools()
        assert len(tools) == 1

        tool = tools[0]
        assert tool.__name__ == "query_weather"

        await agent.stopped()
