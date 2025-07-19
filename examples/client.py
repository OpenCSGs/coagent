import asyncio
import argparse
import uuid

from coagent.agents.chat_agent import ChatHistory, ChatMessage
from coagent.core import Address, init_logger
from coagent.core.util import exit_loop
from coagent.runtimes import NATSRuntime


async def main(agent_name: str):
    session_id = uuid.uuid4().hex
    addr = Address(name=agent_name, id=session_id)
    history: ChatHistory = ChatHistory(messages=[])

    async with NATSRuntime.from_servers() as runtime:
        while True:
            try:
                query = await asyncio.to_thread(input, "User> ")
            except EOFError:
                exit_loop()
                return

            if query == "exit":
                exit_loop()
                return

            msg = ChatMessage(role="user", content=query)
            history.messages.append(msg)
            result = await runtime.send(addr, history, request=True, timeout=50)
            content = result.messages[-1].content
            history.messages.append(ChatMessage(role="assistant", content=content))
            print(f"Assistant> {content}")


if __name__ == "__main__":
    init_logger("ERROR")

    parser = argparse.ArgumentParser()
    parser.add_argument("agent", type=str)
    args = parser.parse_args()

    asyncio.run(main(args.agent))
