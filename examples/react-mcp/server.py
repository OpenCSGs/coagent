from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

mcp = FastMCP(name="Progress Example")


@mcp.tool()
async def get_weather(
    city: str,
    ctx: Context[ServerSession, None],
) -> str:
    """Get the weather for a given city."""
    await ctx.report_progress(
        progress=0,
        total=1.0,
        message=f"Getting weather for {city}",
    )
    return f"The weather in {city} is sunny."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
