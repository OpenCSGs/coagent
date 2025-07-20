import asyncio
import os

from coagent.agents import ChatMessage
from coagent.core import (
    AgentSpec,
    BaseAgent,
    Context,
    handler,
    new,
    init_logger,
)
from coagent.runtimes import NATSRuntime

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.task import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models import AzureOpenAIChatCompletionClient


az_model_client = AzureOpenAIChatCompletionClient(
    model=os.getenv("MODEL_ID"),
    azure_endpoint=os.getenv("MODEL_BASE_URL"),
    api_version=os.getenv("MODEL_API_VERSION"),
    api_key=os.getenv("MODEL_API_KEY"),
    model_capabilities={
        "vision": True,
        "function_calling": True,
        "json_output": True,
    },
)


# Define a tool
async def get_weather(city: str) -> str:
    return f"The weather in {city} is 73 degrees and Sunny."


class AutoGenWeatherAgent(BaseAgent):
    """Weather agent backed by AutoGen."""

    # Define an agent
    weather_agent = AssistantAgent(
        name="weather_agent",
        model_client=az_model_client,
        tools=[get_weather],
    )

    # Define termination condition
    termination = TextMentionTermination("TERMINATE")

    # Define a team
    agent_team = RoundRobinGroupChat([weather_agent], termination_condition=termination)

    @handler
    async def handle(self, msg: ChatMessage, ctx: Context) -> ChatMessage:
        # Run the team and return the result.
        result = await self.agent_team.run(task=msg.content)
        content = result.messages[-2].content
        return ChatMessage(role="assistant", content=content)


agent = AgentSpec("agent", new(AutoGenWeatherAgent))


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(agent)
        await runtime.wait_for_shutdown()


if __name__ == "__main__":
    init_logger("TRACE")
    asyncio.run(main())
