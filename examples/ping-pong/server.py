import argparse
import asyncio

from coagent.core import (
    BaseAgent,
    Context,
    handler,
    idle_loop,
    Message,
    new,
    set_stderr_logger,
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


async def main(server: str, auth: str):
    if server.startswith("nats://"):
        runtime = NATSRuntime.from_servers(server)
    elif server.startswith(("http://", "https://")):
        runtime = HTTPRuntime.from_server(server, auth)
    else:
        raise ValueError(f"Unsupported server: {server}")

    async with runtime:
        await runtime.register("server", new(Server))
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger("TRACE")

    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=str, default="nats://localhost:4222")
    parser.add_argument("--auth", type=str, default="")
    args = parser.parse_args()

    asyncio.run(main(args.server, args.auth))
