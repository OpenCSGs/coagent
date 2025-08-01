import asyncio
import os
from typing import Callable

from coagent.agents import ChatMessage, Model
from coagent.agents.util import run_in_thread
from coagent.core import (
    AgentSpec,
    BaseAgent,
    Context,
    handler,
    new,
    init_logger,
)
from coagent.runtimes import NATSRuntime

from smolagents import LiteLLMModel, tool as smolagents_tool
from smolagents.agents import ToolCallingAgent


class ReActAgent(BaseAgent):
    def __init__(self, tools: list[Callable], model: Model):
        super().__init__()

        litellm_model = LiteLLMModel(
            model_id=model.id,
            api_base=model.base_url,
            api_key=model.api_key,
        )
        # Convert tools to smolagents tools.
        tools = [smolagents_tool(t) for t in tools]

        self.smol_agent = ToolCallingAgent(tools=tools, model=litellm_model)

    @handler
    async def handle(self, msg: ChatMessage, ctx: Context) -> ChatMessage:
        response = await self.run_agent(msg.content)
        return ChatMessage(role="assistant", content=response)

    @run_in_thread
    def run_agent(self, task: str):
        return self.smol_agent.run(task)


def get_weather(location: str, celsius: bool = False) -> str:
    """
    Get weather in the next days at given location.
    Secretly this tool does not care about the location, it hates the weather everywhere.

    Args:
        location: the location
        celsius: the temperature
    """
    return "The weather is UNGODLY with torrential rains and temperatures below -10°C"


agent = AgentSpec(
    "agent",
    new(
        ReActAgent,
        tools=[get_weather],
        model=Model(
            id=os.getenv("MODEL_ID"),
            base_url=os.getenv("MODEL_BASE_URL"),
            api_key=os.getenv("MODEL_API_KEY"),
        ),
    ),
)


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(agent)
        await runtime.wait_for_shutdown()


if __name__ == "__main__":
    init_logger()
    asyncio.run(main())
