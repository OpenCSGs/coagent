import asyncio
import os

from coagent.agents import ChatAgent, StreamChatAgent, Sequential, ModelClient
from coagent.agents.messages import ChatMessage
from coagent.core import AgentSpec, new, set_stderr_logger
from coagent.runtimes import LocalRuntime

client = ModelClient(
    model=os.getenv("MODEL_NAME"),
    api_base=os.getenv("MODEL_API_BASE"),
    api_version=os.getenv("MODEL_API_VERSION"),
    api_key=os.getenv("MODEL_API_KEY"),
)

extractor = AgentSpec(
    "extractor",
    new(
        ChatAgent,
        system="""\
Extract only the numerical values and their associated metrics from the text.
Format each as 'value: metric' on a new line.
Example format:
92: customer satisfaction
45%: revenue growth\
""",
        client=client,
    ),
)

converter = AgentSpec(
    "converter",
    new(
        ChatAgent,
        system="""\
Convert all numerical values to percentages where possible.
If not a percentage or points, convert to decimal (e.g., 92 points -> 92%).
Keep one number per line.
Example format:
92%: customer satisfaction
45%: revenue growth\
""",
        client=client,
    ),
)

sorter = AgentSpec(
    "sorter",
    new(
        ChatAgent,
        system="""\
Sort all lines in descending order by numerical value.
Keep the format 'value: metric' on each line.
Example:
92%: customer satisfaction
87%: employee satisfaction\
""",
        client=client,
    ),
)

formatter = AgentSpec(
    "formatter",
    new(
        StreamChatAgent,
        system="""\
Format the sorted data as a markdown table with columns:
| Metric | Value |
|:--|--:|
| Customer Satisfaction | 92% |\
""",
        client=client,
    ),
)

chain = AgentSpec(
    "chain", new(Sequential, "extractor", "converter", "sorter", "formatter")
)


async def main():
    async with LocalRuntime() as runtime:
        for spec in [extractor, converter, sorter, formatter, chain]:
            await runtime.register(spec)

        result = chain.run_stream(
            ChatMessage(
                role="user",
                content="""\
Q3 Performance Summary:
Our customer satisfaction score rose to 92 points this quarter.
Revenue grew by 45% compared to last year.
Market share is now at 23% in our primary market.
Customer churn decreased to 5% from 8%.
New user acquisition cost is $43 per user.
Product adoption rate increased to 78%.
Employee satisfaction is at 87 points.
Operating margin improved to 34%.\
""",
            ).encode()
        )
        async for chunk in result:
            msg = ChatMessage.decode(chunk)
            print(msg.content, end="", flush=True)


if __name__ == "__main__":
    set_stderr_logger()
    asyncio.run(main())
