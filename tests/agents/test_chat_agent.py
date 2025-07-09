import sys
from typing import AsyncIterator

from pydantic import Field
import pytest

from coagent.agents import ChatAgent
from coagent.agents.chat_agent import (
    CallTool,
    CallToolResult,
    ListToolsResult,
    MCPTextContent,
    MCPTool,
    NamedMCPServer,
    wrap_error,
)
from coagent.core import Address, RawMessage
from coagent.core.runtime import NopChannel
import jsonschema


@pytest.mark.asyncio
async def test_wrap_error_normal():
    @wrap_error
    async def func(
        a: int = Field(..., description="Argument a"),
        b: int = Field(1, description="Argument b"),
    ) -> float:
        return a / b

    assert await func() == "Error: Missing required argument 'a'"
    assert await func(a=1) == 1
    assert await func(a=1, b=0) == "Error: division by zero"


@pytest.mark.asyncio
async def test_wrap_error_aiter():
    @wrap_error
    async def func(
        a: int = Field(..., description="Argument a"),
        b: int = Field(1, description="Argument b"),
    ) -> AsyncIterator[float]:
        yield a / b

    result = await func()
    assert result == "Error: Missing required argument 'a'"

    result = await func(a=1)
    assert await anext(result) == 1

    result = await func(a=1, b=0)
    assert await anext(result) == "Error: division by zero"


class MCPServerTestChannel(NopChannel):
    async def publish(
        self,
        addr: Address,
        msg: RawMessage,
        stream: bool = False,
        request: bool = False,
        reply: str = "",
        timeout: float = 0.5,
        probe: bool = True,
    ) -> AsyncIterator[RawMessage] | RawMessage | None:
        match msg.header.type:
            case "ListTools":
                return ListToolsResult(
                    tools=[
                        MCPTool(
                            name="query_weather",
                            description="Query the weather in the given city.",
                            inputSchema={
                                "title": "query_weatherArguments",
                                "type": "object",
                                "properties": {
                                    "city": {
                                        "title": "City",
                                        "type": "string",
                                    },
                                },
                                "required": ["city"],
                            },
                        )
                    ]
                ).encode()

            case "CallTool":
                call_tool = CallTool.decode(msg)
                city = call_tool.arguments["city"]
                return CallToolResult(
                    content=[
                        MCPTextContent(
                            type="text", text=f"The weather in {city} is sunny."
                        )
                    ],
                ).encode()


class TestChatAgent:
    @pytest.mark.skipif(sys.platform == "win32", reason="Does not run on Windows.")
    @pytest.mark.asyncio
    async def test_get_mcp_tools(self):
        agent = ChatAgent()
        addr = Address(name="test", id="0")
        agent.init(MCPServerTestChannel(), addr)

        tools = await agent._get_mcp_tools([NamedMCPServer(name="server1")])
        assert len(tools) == 1
        # Tool query_weather
        tool = tools[0]

        # Validate the tool
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

        # Call the tool with no arguments
        with pytest.raises(jsonschema.exceptions.ValidationError) as exc:
            await tool()
        assert str(exc.value).startswith("'city' is a required property")

        # Call the tool with required arguments
        result = await tool(city="Beijing")
        assert result == "The weather in Beijing is sunny."
