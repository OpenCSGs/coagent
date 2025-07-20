import argparse
import asyncio

from coagent.agents import DynamicTriage
from coagent.core import AgentSpec, new, init_logger
from coagent.runtimes import NATSRuntime


class OpenCSG(DynamicTriage):
    """OpenCSG Triage Agent."""

    system = "You are a triage agent with a series of tools for different tasks." ""
    namespace = ""


opencsg = AgentSpec("opencsg", new(OpenCSG))


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(opencsg)
        await runtime.wait_for_shutdown()


if __name__ == "__main__":
    init_logger("TRACE")

    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", type=str, default="")
    args = parser.parse_args()

    OpenCSG.namespace = args.namespace
    asyncio.run(main())
