import asyncio

from coagent.agents import ChatAgent, ModelClient
from coagent.core import AgentSpec, idle_loop, new, set_stderr_logger
from coagent.runtimes import NATSRuntime
from pydantic import BaseModel


class FriendInfo(BaseModel):
    name: str
    age: int
    is_available: bool


class FriendList(BaseModel):
    friends: list[FriendInfo]


client = ModelClient(
    model="openai/llama3.1",
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)


structured = AgentSpec(
    "structured",
    new(
        ChatAgent,
        client=client,
    ),
)


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(structured)
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger()
    asyncio.run(main())
