import asyncio
from typing import AsyncIterator

from coagent.agents.chat_agent import ChatMessage, chat
from coagent.core import (
    BaseAgent,
    Context,
    handler,
    Message,
    new,
    set_stderr_logger,
)
from coagent.core.util import idle_loop, pretty_trace_agent_output
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
        async for chunk in chat(msgs):
            yield ChatMessage(role="assistant", content=chunk.content)
            reply += chunk.content

        pretty_trace_agent_output("DevEngineer", reply)
        msg.messages.append(ChatMessage(role="user", content=reply))


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register("dev", new(DevEngineer))
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger("TRACE")

    asyncio.run(main())