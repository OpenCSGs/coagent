import argparse
import asyncio
import json

from coagent.core import (
    Address,
    DiscoveryQuery,
    DiscoveryReply,
    RawMessage,
    set_stderr_logger,
)
from coagent.runtimes import NATSRuntime, HTTPRuntime


async def main(
    server: str, namespace: str, recursive: bool, inclusive: bool, schema: bool
):
    if server.startswith("nats://"):
        runtime = NATSRuntime.from_servers(server)
    elif server.startswith(("http://", "https://")):
        runtime = HTTPRuntime.from_server(server)
    else:
        raise ValueError(f"Unsupported server: {server}")

    async with runtime:
        result: RawMessage = await runtime.channel.publish(
            Address(name="discovery"),
            DiscoveryQuery(
                namespace=namespace,
                recursive=recursive,
                inclusive=inclusive,
            ).encode(),
            request=True,
            probe=False,
        )
        reply: DiscoveryReply = DiscoveryReply.decode(result)

        for agent in reply.agents:
            ops_str = ""
            if schema:
                ops = [op.model_dump() for op in agent.operations]
                ops_str = " " + json.dumps(ops, indent=2)
            print(
                f"\033[1m\033[95m{agent.name}:\033[00m \033[1m\033[92m{agent.description}\033[00m{ops_str}"
            )


if __name__ == "__main__":
    set_stderr_logger("ERROR")

    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=str, default="nats://localhost:4222")
    parser.add_argument("--namespace", type=str, default="")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--inclusive", action="store_true")
    parser.add_argument("--schema", action="store_true")
    args = parser.parse_args()

    asyncio.run(
        main(args.server, args.namespace, args.recursive, args.inclusive, args.schema)
    )
