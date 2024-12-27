import argparse
import asyncio
import json
import uuid

import jq

from coagent.core import Address, RawMessage, set_stderr_logger
from coagent.core.exceptions import BaseError
from coagent.runtimes import NATSRuntime, HTTPRuntime


def make_msg(header: list[str], data: str) -> RawMessage:
    header = dict([h.split(":", 1) for h in header])
    content = data.encode()
    return RawMessage(header=header, content=content)


def jq_filter(data: dict, filter: str) -> str:
    return jq.compile(filter).input(data).first()


def print_msg(msg: RawMessage, oneline: bool, filter: str) -> None:
    output = msg.encode()

    content = output.get("content")
    if content:
        # To make jq happy, we need to convert JSON bytes to Python dict.
        output["content"] = json.loads(content)

    end = "\n" if not oneline else ""
    print(jq_filter(output, filter), flush=True, end=end)


async def run(
    server: str,
    auth: str,
    agent: str,
    msg: RawMessage,
    stream: bool,
    oneline: bool,
    filter: str,
):
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
                print_msg(response, oneline, filter)
            else:
                async for chunk in runtime.channel.publish_multi(addr, msg):
                    print_msg(chunk, oneline, filter)
        except BaseError as exc:
            print(f"Error: {exc}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "agent", type=str, help="The type of the agent to communicate with."
    )
    parser.add_argument(
        "-d",
        "--data",
        type=str,
        default="",
        help="The message body in form of JSON string. (Defaults to %(default)r)",
    )
    parser.add_argument(
        "-H", "--header", type=str, action="append", help="The message header."
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Whether in stream mode. (Defaults to %(default)r)",
    )
    parser.add_argument(
        "--oneline",
        action="store_true",
        help="Whether to output stream messages in one line. This option only works in stream mode. (Defaults to %(default)r)",
    )
    parser.add_argument(
        "-F",
        "--filter",
        type=str,
        default=".",
        help="Output filter compatible with jq. (Defaults to %(default)r)",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="This is a shorthand for \"--stream -F '.content.content' --oneline\" used together.",
    )
    parser.add_argument(
        "--server",
        type=str,
        default="nats://localhost:4222",
        help="The runtime server address. (Defaults to %(default)r)",
    )
    parser.add_argument(
        "--auth",
        type=str,
        default="",
        help="The runtime server authentication token. (Defaults to %(default)r)",
    )
    parser.add_argument(
        "--level",
        type=str,
        default="ERROR",
        help="The logging level. (Defaults to %(default)r)",
    )
    args = parser.parse_args()

    if not args.header:
        parser.error("At least one header (-H/--header) is required.")

    if args.chat:
        args.stream = True
        args.oneline = True
        args.filter = ".content.content"

    set_stderr_logger(args.level)
    msg = make_msg(args.header, args.data)
    asyncio.run(
        run(
            args.server,
            args.auth,
            args.agent,
            msg,
            args.stream,
            args.oneline,
            args.filter,
        )
    )


if __name__ == "__main__":
    main()
