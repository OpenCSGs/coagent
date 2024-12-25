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


class QaEngineer(BaseAgent):
    system = """\
You are a Software Quality Control Engineer that specializes in checking code
for errors. You have an eye for detail and a knack for finding
hidden bugs.

You check for missing imports, variable declarations, mismatched brackets,
syntax errors and logic errors.\
"""
    task = """\
You will create a program using Python, these are the instructions:

Instructions
------------
{query}

Code
----
{code}

Using the code you got, check for errors. Check for logic errors,
syntax errors, missing imports, variable declarations, mismatched brackets,
and security vulnerabilities.

Your Final answer must be as below:
## Issues
Critical issues you found. If no issues found, write 'LGTM'.

## Code

The corrected version of full python code.\
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
                    query=msg.messages[-2].content,
                    code=msg.messages[-1].content,
                ),
            ),
        ]

        reply = ""
        async for chunk in chat(msgs):
            yield ChatMessage(role="assistant", content=chunk.content)
            reply += chunk.content

        pretty_trace_agent_output("QaEngineer", reply)
        msg.messages.append(ChatMessage(role="user", content=reply))


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register("qa", new(QaEngineer))
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger("TRACE")

    asyncio.run(main())
