import asyncio
from coagent.agents.react_agent import (
    ReActAgent,
    InputMessage,
    InputHistory,
    OutputMessage,
    MessageOutputItem,
    ToolCallItem,
    ToolCallOutputItem,
    ToolCallProgressItem,
)
from coagent.core import AgentSpec, new, init_logger
from coagent.runtimes import LocalRuntime
import mcputil


async def main():
    async with LocalRuntime() as runtime:
        # Alternative usage:
        #   ```
        #   mcp_client = mcputil.Client(mcputil.StreamableHTTP(url="http://localhost:8000"))
        #   await mcp_client.connect()
        #   ...
        #   await mcp_client.close()
        #   ```
        async with mcputil.Client(
            mcputil.StreamableHTTP(url="http://localhost:8000")
        ) as mcp_client:
            reporter = AgentSpec(
                "reporter",
                new(
                    ReActAgent,
                    name="reporter",
                    system="You are a helpful weather reporter",
                    tools=[mcp_client],
                ),
            )
            await runtime.register(reporter)

            result = await reporter.run(
                InputHistory(
                    messages=[
                        InputMessage(
                            role="user", content="What's the weather like in Beijing?"
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
