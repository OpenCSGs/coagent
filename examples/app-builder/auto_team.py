import asyncio

from coagent.core import idle_loop, new, set_stderr_logger
from coagent.agents import ChatAgent, tool
from coagent.runtimes import NATSRuntime


class AutoTeam(ChatAgent):
    system = """You are an manager who manages a team that consists of a dev agent and a qa agent.
    
    Your team is responsible for build software for users, and you should follow these rules:
    - Upon the request of the user, you should first transfer the conversation to the dev agent if the user requests to generate code.
    - When receiving the code from the dev agent, you should transfer the conversation to the qa agent.
    - Finally show the result from the qa agent to the user.
    """

    @tool
    async def transfer_to_dev(self):
        """The dev agent to generate the software code."""
        return await self.agent("dev")

    @tool
    async def transfer_to_qa(self):
        """The qa agent to review and refine the given software code."""
        return await self.agent("qa")


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register("auto_team", new(AutoTeam))
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger("TRACE")

    asyncio.run(main())
