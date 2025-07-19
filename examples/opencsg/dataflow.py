import argparse
import asyncio

from coagent.agents import ChatAgent, RunContext, submit, tool
from coagent.core import AgentSpec, idle_loop, new, init_logger
from coagent.runtimes import NATSRuntime

import httpx
from pydantic import Field


class DataFlow(ChatAgent):
    """An agent that help users deal with tasks related to datasets."""

    system = "You are an agent that help users deal with tasks related to datasets."

    @tool
    @submit()
    async def search_dataset(
        self, ctx: RunContext, name: str = Field(description="The name of the dataset")
    ) -> str:
        """Search datasets by the given name."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://hub.opencsg.com/api/v1/datasets",
                params=dict(search=name),
            )
            if resp.status_code != 200:
                return f"Error: {resp.text}"
            datasets = resp.json()["data"]
            if not datasets:
                return "Sorry, no datasets found."
            return ", ".join([d["name"] for d in datasets])


async def main(name: str):
    dataflow = AgentSpec(name, new(DataFlow))
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(dataflow)
        await idle_loop()


if __name__ == "__main__":
    init_logger("TRACE")

    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str, default="dataflow")
    args = parser.parse_args()

    asyncio.run(main(args.name))
