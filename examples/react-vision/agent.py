import asyncio
from coagent.agents.react_agent import (
    ReActAgent,
    InputMessage,
    InputMessageTextParam,
    InputMessageImageParam,
    InputHistory,
    OutputMessage,
    MessageOutputItem,
    ToolCallItem,
    ToolCallOutputItem,
    ToolCallProgressItem,
)
from coagent.core import AgentSpec, new, init_logger
from coagent.runtimes import LocalRuntime


analyzer = AgentSpec(
    "analyzer",
    new(
        ReActAgent,
        name="reporter",
        system="You are a helpful image analyzer",
    ),
)


async def main():
    async with LocalRuntime() as runtime:
        await runtime.register(analyzer)

        result = await analyzer.run(
            InputHistory(
                messages=[
                    InputMessage(
                        role="user",
                        content=[
                            InputMessageTextParam(
                                type="input_text", text="What’s in this image?"
                            ),
                            InputMessageImageParam(
                                detail="auto",
                                type="input_image",
                                image_url="https://raw.githubusercontent.com/OpenCSGs/coagent/main/assets/coagent-overview.png",
                            ),
                        ],
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
