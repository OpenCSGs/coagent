import asyncio
import os

from coagent.agents import ChatAgent, ChatMessage, ModelClient
from coagent.core import AgentSpec, new, set_stderr_logger
from coagent.runtimes import LocalRuntime


client = ModelClient(
    model="openai/deepseek-reasoner",
    api_base="https://api.deepseek.com/v1",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
)


deepseek_reasoner = AgentSpec("deepseek_reasoner", new(ChatAgent, client=client))


async def main():
    async with LocalRuntime() as runtime:
        await runtime.register(deepseek_reasoner)

        result = await deepseek_reasoner.run(
            ChatMessage(
                role="user", content="9.11 and 9.8, which is greater?"
            ).encode(),
            stream=True,
        )

        reasoning_started = False
        reasoning_stopped = False
        async for chunk in result:
            msg = ChatMessage.decode(chunk)
            if msg.reasoning_content:
                if not reasoning_started:
                    print("<think>", flush=True)
                    reasoning_started = True
                print(msg.reasoning_content, end="", flush=True)
            if msg.content:
                if reasoning_started and not reasoning_stopped:
                    print("</think>", flush=True)
                    reasoning_stopped = True
                print(msg.content, end="", flush=True)


if __name__ == "__main__":
    set_stderr_logger()
    asyncio.run(main())
