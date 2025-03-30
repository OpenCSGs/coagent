from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Weather")


@mcp.prompt()
def system_prompt(role: str) -> str:
    """Create a system prompt."""
    return f"You are a helpful {role}."


@mcp.tool()
def query_weather(city: str) -> str:
    """Query the weather in the given city."""
    return f"The weather in {city} is sunny."


@mcp.tool()
def book_flight(departure: str, arrival: str) -> str:
    """Book a flight from departure to arrival."""
    return f"Flight from {departure} to {arrival} has been booked."


if __name__ == "__main__":
    mcp.run()
