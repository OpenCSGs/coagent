import argparse
import asyncio

from coagent.core import (
    AgentSpec,
    BaseAgent,
    Context,
    GenericMessage,
    handler,
    idle_loop,
    new,
    init_logger,
)
from coagent.runtimes import NATSRuntime, HTTPRuntime


class Employee(BaseAgent):
    @handler
    async def handle(self, msg: GenericMessage, ctx: Context) -> GenericMessage:
        return msg


async def main(name: str, description: str, server: str):
    if server.startswith("nats://"):
        runtime = NATSRuntime.from_servers(server)
    elif server.startswith(("http://", "https://")):
        runtime = HTTPRuntime.from_server(server)
    else:
        raise ValueError(f"Unsupported server: {server}")

    employee = AgentSpec(name, new(Employee), description=description)

    async with runtime:
        await runtime.register(employee)
        await idle_loop()


if __name__ == "__main__":
    init_logger("TRACE")

    parser = argparse.ArgumentParser()
    parser.add_argument("name", type=str)
    parser.add_argument("description", type=str)
    parser.add_argument("--server", type=str, default="nats://localhost:4222")
    args = parser.parse_args()

    asyncio.run(main(args.name, args.description, args.server))
