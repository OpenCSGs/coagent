import argparse
import asyncio
from enum import Enum

from coagent.agents import ChatAgent, confirm, RunContext, tool
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


class Task(str, Enum):
    unknown = ""
    text_generation = "text-generation"
    text_to_image = "text-to-image"
    image_to_image = "image-to-image"
    text_to_speech = "text-to-speech"
    conversational = "conversational"


class CSGHub(ChatAgent):
    """An agent that help users deal with tasks related to models."""

    system = "You are an assistant that help users deal with tasks related to models."

    @tool
    @confirm("About to search model {name}, are you sure?")
    async def search_model(
        self,
        ctx: RunContext,
        name: str = Field(description="The name of the model"),
        language: Language = Field(description="The language that the model supports"),
        task: Task = Field(description="The task that the model supports"),
    ) -> str | ChatMessage:
        """Search models by the given name and language."""
        print(f"RunContext: {ctx}")

        params = dict()
        if name:
            params["search"] = name
        if language:
            params["language"] = language
        if task:
            params["task"] = task

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://hub.opencsg-stg.com/api/v1/models",
                params=params,
            )
            models = resp.json()["data"]
            if not models:
                return "Sorry, no models found."
            return ", ".join([m["name"] for m in models])

    @tool
    async def upload_model(
        self,
        name: str = Field(description="The name of the model"),
        addr: str = Field(description="The address to upload the model"),
    ) -> str:
        """Upload the model to the given address."""
        return "Success"


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
