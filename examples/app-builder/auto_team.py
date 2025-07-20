import asyncio

from coagent.agents import ChatAgent, tool
from coagent.core import AgentSpec, new, init_logger
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
        async for chunk in self.agent("dev"):
            yield chunk

    @tool
    async def transfer_to_qa(self):
        """The qa agent to review and refine the given software code."""
        async for chunk in self.agent("qa"):
            yield chunk


auto_team = AgentSpec("auto_team", new(AutoTeam))


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(auto_team)
        await runtime.wait_for_shutdown()


if __name__ == "__main__":
    init_logger("TRACE")

    asyncio.run(main())
