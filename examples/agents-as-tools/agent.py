import asyncio

from coagent.agents.react_agent import (
    ReActAgent,
    InputMessage,
    InputHistory,
    OutputMessage,
    MessageOutputItem,
    Subagent,
    ToolCallItem,
    ToolCallOutputItem,
    ToolCallProgressItem,
)
from coagent.core import AgentSpec, new, init_logger
from coagent.runtimes import LocalRuntime

"""
This example shows the agents-as-tools pattern. The frontline agent receives a user message and
then picks which agents to call, as tools. In this case, it picks from a set of translation
agents.
"""


spanish_agent = AgentSpec(
    "spanish_agent",
    new(
        ReActAgent,
        name="spanish_agent",
        system="You translate the user's message to Spanish",
    ),
)

french_agent = AgentSpec(
    "french_agent",
    new(
        ReActAgent,
        name="french_agent",
        system="You translate the user's message to French",
    ),
)

orchestrator_agent = AgentSpec(
    "orchestrator_agent",
    new(
        ReActAgent,
        name="orchestrator_agent",
        system=(
            "You are a translation agent. You use the tools given to you to translate."
            "If asked for multiple translations, you call the relevant tools in order."
            "You never translate on your own, you always use the provided tools."
        ),
        tools=[
            Subagent("spanish_agent").as_tool(
                name="translate_to_spanish",
                description="Translate the user's message to Spanish",
            ),
            Subagent("french_agent").as_tool(
                name="translate_to_french",
                description="Translate the user's message to French",
            ),
        ],
    ),
)


async def main():
    async with LocalRuntime() as runtime:
        await runtime.register(spanish_agent)
        await runtime.register(french_agent)
        await runtime.register(orchestrator_agent)

        result = await orchestrator_agent.run(
            InputHistory(
                messages=[
                    InputMessage(
                        role="user",
                        content="Translate this to Spanish: Hello, how are you doing today?",
                    )
                ]
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
