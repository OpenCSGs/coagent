import asyncio

from coagent.agents import ChatAgent, ChatMessage, ModelClient, StructuredOutput
from coagent.core import AgentSpec, new, set_stderr_logger
from coagent.runtimes import LocalRuntime
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
    async with LocalRuntime() as runtime:
        await runtime.register(structured)

        result = await structured.run(
            StructuredOutput(
                input=ChatMessage(
                    role="user",
                    content="\
I have two friends. The first is Ollama 22 years old busy saving the world, \
and the second is Alonso 23 years old and wants to hang out. Return a list \
of friends in JSON format",
                ),
                output_type=FriendList,
            ).encode(),
            stream=True,
        )
        async for chunk in result:
            msg = ChatMessage.decode(chunk)
            print(msg.content, end="", flush=True)


if __name__ == "__main__":
    set_stderr_logger()
    asyncio.run(main())
