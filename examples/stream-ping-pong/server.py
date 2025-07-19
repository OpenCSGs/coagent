import argparse
import asyncio
from typing import AsyncIterator

from pydantic import Field

from coagent.core import (
    AgentSpec,
    BaseAgent,
    Context,
    handler,
    idle_loop,
    Message,
    new,
    init_logger,
)
from coagent.runtimes import NATSRuntime, HTTPRuntime


class Ping(Message):
    pass


class PartialPong(Message):
    content: str = Field(..., description="The content of the Pong message.")


class StreamServer(BaseAgent):
    """The Stream Pong Server."""

    @handler
    async def handle(self, msg: Ping, ctx: Context) -> AsyncIterator[PartialPong]:
        """Handle the Ping message and return a stream of PartialPong messages."""
        words = ("Hi ", "there, ", "this ", "is ", "the ", "Pong ", "server.")
        for word in words:
            await asyncio.sleep(0.6)
            yield PartialPong(content=word)


stream_server = AgentSpec("stream_server", new(StreamServer))


async def main(server: str, auth: str):
    if server.startswith("nats://"):
        runtime = NATSRuntime.from_servers(server)
    elif server.startswith(("http://", "https://")):
        runtime = HTTPRuntime.from_server(server, auth)
    else:
        raise ValueError(f"Unsupported server: {server}")

    async with runtime:
        await runtime.register(stream_server)
        await idle_loop()


if __name__ == "__main__":
    init_logger("TRACE")

    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=str, default="nats://localhost:4222")
    parser.add_argument("--auth", type=str, default="")
    args = parser.parse_args()

    asyncio.run(main(args.server, args.auth))
