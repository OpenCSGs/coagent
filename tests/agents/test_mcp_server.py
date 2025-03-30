import sys

import pytest

from coagent.agents.mcp_server import (
    CallTool,
    Connect,
    ListTools,
    MCPServer,
    MCPServerStdioParams,
)
from coagent.core import Context


class TestMCPServer:
    @pytest.mark.skipif(sys.platform == "win32", reason="Does not run on Windows.")
    @pytest.mark.asyncio
    async def test_connect(self):
        agent = MCPServer()
        ctx = Context()

        # Connect successfully
        await agent.connect(
            Connect(
                transport="stdio",
                params=MCPServerStdioParams(
                    command="python",
                    args=["tests/agents/example_mcp_server.py"],
                ),
            ),
            ctx,
        )

        # Connect error
        with pytest.raises(Exception) as exc:
            await agent.connect(
                Connect(
                    transport="stdio",
                    params=MCPServerStdioParams(
                        command="pythonx",
                        args=["tests/agents/example_mcp_server.py"],
                    ),
                ),
                ctx,
            )
        assert str(exc.value).startswith(
            "[Errno 2] No such file or directory: 'pythonx'"
        )

    @pytest.mark.skipif(sys.platform == "win32", reason="Does not run on Windows.")
    @pytest.mark.asyncio
    async def test_list_tools(self):
        agent = MCPServer()
        ctx = Context()

        # Connect to the server
        await agent.connect(
            Connect(
                transport="stdio",
                params=MCPServerStdioParams(
                    command="python",
                    args=["tests/agents/example_mcp_server.py"],
                ),
            ),
            ctx,
        )

        result = await agent.list_tools(ListTools(), ctx)
        assert len(result.tools) == 2

        # Validate tool query_weather
        tool = result.tools[0]
        assert tool.name == "query_weather"
        assert tool.description == "Query the weather in the given city."
        assert tool.inputSchema == {
            "properties": {
                "city": {
                    "title": "City",
                    "type": "string",
                }
            },
            "required": ["city"],
            "title": "query_weatherArguments",
            "type": "object",
        }

        # Validate tool book_flight
        tool = result.tools[1]
        assert tool.name == "book_flight"
        assert tool.description == "Book a flight from departure to arrival."
        assert tool.inputSchema == {
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
        }

        await agent.stopped()

    @pytest.mark.skipif(sys.platform == "win32", reason="Does not run on Windows.")
    @pytest.mark.asyncio
    async def test_call_tool(self):
        agent = MCPServer()
        ctx = Context()

        # Connect to the server
        await agent.connect(
            Connect(
                transport="stdio",
                params=MCPServerStdioParams(
                    command="python",
                    args=["tests/agents/example_mcp_server.py"],
                ),
            ),
            ctx,
        )

        result = await agent.call_tool(
            CallTool(
                name="query_weather",
                arguments={"city": "Beijing"},
            ),
            ctx,
        )
        assert result.isError is False
        assert result.content[0].text == "The weather in Beijing is sunny."
