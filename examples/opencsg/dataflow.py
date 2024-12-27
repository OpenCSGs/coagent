import argparse
import asyncio

from coagent.agents import ChatAgent, tool
from coagent.core import idle_loop, new, set_stderr_logger
from coagent.runtimes import NATSRuntime

import httpx
from pydantic import Field


class DataFlow(ChatAgent):
    """An agent that help users deal with tasks related to datasets."""

    system = "You are an agent that help users deal with tasks related to datasets."

    @tool
    async def search_dataset(
        self, name: str = Field(description="The name of the dataset")
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
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(name, new(DataFlow))
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger("TRACE")

    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str, default="dataflow")
    args = parser.parse_args()

    asyncio.run(main(args.name))
