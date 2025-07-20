import asyncio
from typing import AsyncIterator

from coagent.agents.chat_agent import ChatMessage
from coagent.agents.util import chat
from coagent.core import (
    AgentSpec,
    BaseAgent,
    Context,
    handler,
    Message,
    new,
    init_logger,
)
from coagent.core.util import pretty_trace_agent_output
from coagent.runtimes import NATSRuntime


class ChatHistory(Message):
    messages: list[ChatMessage]


class DevEngineer(BaseAgent):
    system = """\
You are a Senior Software Engineer at a leading tech think tank.
Your expertise in programming in Python. and do your best to produce perfect code.\
"""
    task = """\
You will create a program using Python, these are the instructions:

Instructions
------------
{query}

Your Final answer must be the full python code, only the python code and nothing else.\
"""

    @handler
    async def handle(
        self, msg: ChatHistory, ctx: Context
    ) -> AsyncIterator[ChatMessage]:
        msgs = [
            ChatMessage(role="system", content=self.system),
            ChatMessage(
                role="user",
                content=self.task.format(
                    query=msg.messages[-1].content,
                ),
            ),
        ]

        reply = ""
        response = await chat(msgs, stream=True)
        async for chunk in response:
            yield ChatMessage(role="assistant", content=chunk.content)
            reply += chunk.content

        pretty_trace_agent_output("DevEngineer", reply)
        msg.messages.append(ChatMessage(role="user", content=reply))


dev = AgentSpec("dev", new(DevEngineer))


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(dev)
        await runtime.wait_for_shutdown()


if __name__ == "__main__":
    init_logger("TRACE")

    asyncio.run(main())
