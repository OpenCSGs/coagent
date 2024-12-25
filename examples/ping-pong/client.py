import argparse
import asyncio
import uuid

from coagent.core import Address, RawMessage, set_stderr_logger
from coagent.runtimes import NATSRuntime, HTTPRuntime


async def main(server: str, auth: str):
    session_id = uuid.uuid4().hex

    if server.startswith("nats://"):
        runtime = NATSRuntime.from_servers(server)
    elif server.startswith(("http://", "https://")):
        runtime = HTTPRuntime.from_server(server, auth)
    else:
        raise ValueError(f"Unsupported server: {server}")

    async with runtime:
        addr = Address(name="server", id=session_id)
        ping = RawMessage(
            header=dict(
                type="Ping",
                content_type="application/json",
            )
        )
        pong = await runtime.channel.publish(addr, ping, request=True, timeout=10)
        print(pong.encode())
        await runtime.delete(addr)  # Delete the server agent


if __name__ == "__main__":
    set_stderr_logger("ERROR")

    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=str, default="nats://localhost:4222")
    parser.add_argument("--auth", type=str, default="")
    args = parser.parse_args()

    asyncio.run(main(args.server, args.auth))
