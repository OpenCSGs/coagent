import argparse
import asyncio
from enum import Enum

from coagent.agents import ChatAgent, confirm, RunContext, tool
from coagent.agents.messages import ChatMessage
from coagent.core import AgentSpec, new, init_logger
from coagent.runtimes import NATSRuntime

import httpx
from pydantic import Field


class Language(str, Enum):
    unknown = ""
    en = "en"
    zh = "zh"
    ja = "ja"
    de = "de"


class CSGHub(ChatAgent):
    """An agent that help users deal with tasks related to models."""

    system = "You are an assistant that help users deal with tasks related to models."

    @tool
    @confirm("About to search model {name}, are you sure?")
    async def search_model(
        self,
        ctx: RunContext,
        name: str = Field(description="The name of the model"),
        language: Language = Field(description="The language that the model supports"),  # noqa: B008
        limit: int = Field(
            default=10, description="The maximum number of models to return"
        ),
    ) -> str | ChatMessage:
        """Search models by the given name and language."""
        params = dict()
        if name:
            params["search"] = name
        if language:
            params["language"] = language
        if limit:
            params["per"] = limit

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://hub.opencsg.com/api/v1/models",
                params=params,
            )
            if resp.status_code != 200:
                return f"Error: {resp.text}"
            models = resp.json()["data"]
            if not models:
                return "Sorry, no models found."
            return ", ".join([m["name"] for m in models])


async def main(name: str):
    csghub = AgentSpec(name, new(CSGHub))
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(csghub)
        await runtime.wait_for_shutdown()


if __name__ == "__main__":
    init_logger("TRACE")

    parser = argparse.ArgumentParser()
    parser.add_argument("name", type=str, default="csghub")
    args = parser.parse_args()

    asyncio.run(main(args.name))
