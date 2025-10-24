import asyncio
import os

from coagent.agents import Model
from coagent.agents.react_agent import (
    ReActAgent,
    InputMessage,
    InputHistory,
    RunContext,
    OutputMessage,
    MessageOutputItem,
    ToolCallItem,
    ToolCallOutputItem,
    ToolCallProgressItem,
)
from coagent.core import AgentSpec, new, init_logger
from coagent.runtimes import LocalRuntime


async def get_current_city(ctx: RunContext) -> str:
    """Get the current city."""
    ctx.report_progress(message="Getting the current city...")
    return "Beijing"


async def query_weather(ctx: RunContext, city: str) -> str:
    """Query the weather in the given city."""
    ctx.report_progress(message=f"Querying the weather in {city}...")
    return f"The weather in {city} is sunny."


reporter = AgentSpec(
    "reporter",
    new(
        ReActAgent,
        name="weporter",
        system="You are a helpful weather reporter",
        model=Model(
            id=os.getenv("MODEL_ID"),
            base_url=os.getenv("MODEL_BASE_URL"),
            api_key=os.getenv("MODEL_API_KEY"),
        ),
        tools=[get_current_city, query_weather],
    ),
)


async def main():
    async with LocalRuntime() as runtime:
        await runtime.register(reporter)

        result = await reporter.run(
            InputHistory(
                messages=[InputMessage(role="user", content="What's the weather?")]
            ).encode(),
            stream=True,
        )
        async for chunk in result:
            msg = OutputMessage.decode(chunk)
            i = msg.item
            match i:
                case MessageOutputItem():
                    print(i.raw_item.content[0].text, end="", flush=True)
                case ToolCallItem():
                    print(
                        f"\n[tool#{i.raw_item.call_id} call: {i.raw_item.name}]",
                        flush=True,
                    )
                case ToolCallProgressItem():
                    print(
                        f"\n[tool#{i.raw_item.call_id} progress: {i.raw_item.message}]",
                        flush=True,
                    )
                case ToolCallOutputItem():
                    print(
                        f"\n[tool#{i.raw_item.call_id} output: {i.raw_item.output}]",
                        flush=True,
                    )


if __name__ == "__main__":
    init_logger()
    asyncio.run(main())
