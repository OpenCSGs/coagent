import asyncio
import os

from coagent.agents.chat_agent import ChatHistory, ChatMessage
from coagent.core import (
    AgentSpec,
    BaseAgent,
    Context,
    handler,
    idle_loop,
    new,
    set_stderr_logger,
)
from coagent.runtimes import NATSRuntime
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.task import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models import AzureOpenAIChatCompletionClient


az_model_client = AzureOpenAIChatCompletionClient(
    model=os.getenv("AZURE_MODEL"),
    azure_endpoint=os.getenv("AZURE_API_BASE"),
    api_version=os.getenv("AZURE_API_VERSION"),
    api_key=os.getenv("AZURE_API_KEY"),
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
    async def handle(self, msg: ChatHistory, ctx: Context) -> ChatHistory:
        # Run the team and return the result.
        result = await self.agent_team.run(task=msg.messages[-1].content)
        content = result.messages[-2].content
        msg.messages.append(ChatMessage(role="assistant", content=content))
        return msg


autogen = AgentSpec("autogen", new(AutoGenWeatherAgent))


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(autogen)
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger("TRACE")

    asyncio.run(main())
