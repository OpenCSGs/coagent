import argparse
import asyncio
from enum import Enum

from coagent.agents import ChatAgent, confirm, tool
from coagent.agents.messages import ChatMessage
from coagent.core import idle_loop, new, set_stderr_logger
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
        name: str = Field(description="The name of the model"),
        language: Language = Field(description="The language that the model supports"),
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
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(name, new(CSGHub))
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger("TRACE")

    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str, default="csghub")
    args = parser.parse_args()

    asyncio.run(main(args.name))
