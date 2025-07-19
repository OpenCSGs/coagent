import asyncio
import os

from coagent.agents import ChatAgent, ModelClient, tool
from coagent.agents.messages import ChatMessage
from coagent.core import AgentSpec, new, init_logger
from coagent.runtimes import LocalRuntime


class Assistant(ChatAgent):
    system = """You are an agent who can use tools."""
    client = ModelClient(
        model=os.getenv("MODEL_ID"),
        base_url=os.getenv("MODEL_BASE_URL"),
        api_version=os.getenv("MODEL_API_VERSION"),
        api_key=os.getenv("MODEL_API_KEY"),
    )

    @tool
    async def query_weather(self, city: str) -> str:
        """Query the weather in the given city."""
        return f"The weather in {city} is sunny."


assistant = AgentSpec("assistant", new(Assistant))


async def main():
    async with LocalRuntime() as runtime:
        await runtime.register(assistant)

        result = await assistant.run(
            ChatMessage(
                role="user",
                content="What's the weather like in Beijing?",
            ).encode(),
            stream=True,
        )
        async for chunk in result:
            msg = ChatMessage.decode(chunk)
            print(msg.content, end="", flush=True)


if __name__ == "__main__":
    init_logger("TRACE")
    asyncio.run(main())
