import asyncio

from coagent.agents import ChatAgent, Model
from coagent.core import AgentSpec, idle_loop, new, init_logger
from coagent.runtimes import NATSRuntime
from pydantic import BaseModel


class FriendInfo(BaseModel):
    name: str
    age: int
    is_available: bool


class FriendList(BaseModel):
    friends: list[FriendInfo]


model = Model(
    id="openai/llama3.1",
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)


structured = AgentSpec(
    "structured",
    new(
        ChatAgent,
        model=model,
    ),
)


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(structured)
        await idle_loop()


if __name__ == "__main__":
    init_logger()
    asyncio.run(main())
