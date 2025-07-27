import argparse
import asyncio

from coagent.agents import Triage
from coagent.core import AgentSpec, new, init_logger, DiscoveryQuery
from coagent.runtimes import NATSRuntime


class OpenCSG(Triage):
    """OpenCSG Triage Agent."""

    system = "You are a triage agent with a series of tools for different tasks." ""
    dynamic_agents = [DiscoveryQuery(namespace="")]


opencsg = AgentSpec("opencsg", new(OpenCSG))


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(opencsg)
        await runtime.wait_for_shutdown()


if __name__ == "__main__":
    init_logger("TRACE")

    parser = argparse.ArgumentParser()
    parser.add_argument("namespace", type=str, default="")
    args = parser.parse_args()

    OpenCSG.dynamic_agents[0].namespace = args.namespace
    asyncio.run(main())
