from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Weather")


@mcp.tool()
def query_weather(city: str) -> str:
    """Query the weather in the given city."""
    return f"The weather in {city} is sunny."


if __name__ == "__main__":
    mcp.run()
