import argparse
import asyncio

from coagent.core import (
    AgentSpec,
    BaseAgent,
    Context,
    handler,
    Message,
    new,
    init_logger,
)
from coagent.runtimes import NATSRuntime, HTTPRuntime


class Ping(Message):
    pass


class Pong(Message):
    pass


class Server(BaseAgent):
    """The Pong Server."""

    @handler
    async def handle(self, msg: Ping, ctx: Context) -> Pong:
        """Handle the Ping message and return a Pong message."""
        return Pong()


pong_server = AgentSpec("server", new(Server))


async def main(server: str, auth: str):
    if server.startswith("nats://"):
        runtime = NATSRuntime.from_servers(server)
    elif server.startswith(("http://", "https://")):
        runtime = HTTPRuntime.from_server(server, auth)
    else:
        raise ValueError(f"Unsupported server: {server}")

    async with runtime:
        await runtime.register(pong_server)
        await runtime.wait_for_shutdown()


if __name__ == "__main__":
    init_logger("TRACE")

    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=str, default="nats://localhost:4222")
    parser.add_argument("--auth", type=str, default="")
    args = parser.parse_args()

    asyncio.run(main(args.server, args.auth))
