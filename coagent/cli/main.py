import argparse
import asyncio
import uuid

from coagent.core import Address, RawMessage, set_stderr_logger
from coagent.core.exceptions import BaseError
from coagent.runtimes import NATSRuntime, HTTPRuntime


def make_msg(header: list[str], data: str) -> RawMessage:
    header = dict([h.split(":", 1) for h in header])
    content = data.encode()
    return RawMessage(header=header, content=content)


async def run(server: str, auth: str, agent: str, msg: RawMessage, stream: bool):
    session_id = uuid.uuid4().hex

    if server.startswith("nats://"):
        runtime = NATSRuntime.from_servers(server)
    elif server.startswith(("http://", "https://")):
        runtime = HTTPRuntime.from_server(server, auth)
    else:
        raise ValueError(f"Unsupported server: {server}")

    async with runtime:
        addr = Address(name=agent, id=session_id)
        try:
            if not stream:
                response = await runtime.channel.publish(
                    addr, msg, request=True, timeout=10
                )
                print(response.encode())
            else:
                async for chunk in runtime.channel.publish_multi(addr, msg):
                    print(chunk.encode())
        except BaseError as exc:
            print(f"Error: {exc}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "agent", type=str, help="The type of the agent to communicate with."
    )
    parser.add_argument(
        "-d", "--data", type=str, default="", help="The message body (in form of JSON)."
    )
    parser.add_argument(
        "-H", "--header", type=str, action="append", help="The message header."
    )
    parser.add_argument("--stream", action="store_true", help="Whether in stream mode.")
    parser.add_argument(
        "--server",
        type=str,
        default="nats://localhost:4222",
        help="The runtime server address.",
    )
    parser.add_argument(
        "--auth", type=str, default="", help="The runtime server authentication token."
    )
    parser.add_argument("--level", type=str, default="ERROR", help="The logging level.")
    args = parser.parse_args()

    if not args.header:
        parser.error(f"At least one header (-H/--header) is required.")

    set_stderr_logger(args.level)
    msg = make_msg(args.header, args.data)
    asyncio.run(run(args.server, args.auth, args.agent, msg, args.stream))


if __name__ == "__main__":
    main()
