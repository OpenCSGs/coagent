from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Weather", port=8080)


@mcp.prompt()
def system_prompt(role: str) -> str:
    """Create a system prompt."""
    return f"You are a helpful {role}."


@mcp.tool()
def query_weather(city: str) -> str:
    """Query the weather in the given city."""
    return f"The weather in {city} is sunny."


if __name__ == "__main__":
    mcp.run(transport="sse")
