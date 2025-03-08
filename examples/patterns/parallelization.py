import asyncio
import os

from coagent.agents import (
    Aggregator,
    AggregationResult,
    ChatAgent,
    ChatMessage,
    ModelClient,
    Parallel,
)
from coagent.core import AgentSpec, new, set_stderr_logger
from coagent.runtimes import LocalRuntime

client = ModelClient(
    model=os.getenv("MODEL_ID"),
    base_url=os.getenv("MODEL_BASE_URL"),
    api_version=os.getenv("MODEL_API_VERSION"),
    api_key=os.getenv("MODEL_API_KEY"),
)

customer = AgentSpec(
    "customer",
    new(
        ChatAgent,
        system="""\
Customers:
- Price sensitive
- Want better tech
- Environmental concerns\
""",
        client=client,
    ),
)

employee = AgentSpec(
    "employee",
    new(
        ChatAgent,
        system="""\
Employees:
- Job security worries
- Need new skills
- Want clear direction\
""",
        client=client,
    ),
)

investor = AgentSpec(
    "investor",
    new(
        ChatAgent,
        system="""\
Investors:
- Expect growth
- Want cost control
- Risk concerns\
""",
        client=client,
    ),
)

supplier = AgentSpec(
    "supplier",
    new(
        ChatAgent,
        system="""\
Suppliers:
- Capacity constraints
- Price pressures
- Tech transitions\
""",
        client=client,
    ),
)

aggregator = AgentSpec("aggregator", new(Aggregator))

parallel = AgentSpec(
    "parallel",
    new(
        Parallel,
        "customer",
        "employee",
        "investor",
        "supplier",
        aggregator="aggregator",
    ),
)


async def main():
    async with LocalRuntime() as runtime:
        for spec in [customer, employee, investor, supplier, aggregator, parallel]:
            await runtime.register(spec)

        result = await parallel.run(
            ChatMessage(
                role="user",
                content="""\
Analyze how market changes will impact this stakeholder group.
Provide specific impacts and recommended actions.
Format with clear sections and priorities.\
""",
            ).encode()
        )
        msg = AggregationResult.decode(result)
        for result in msg.results:
            x = ChatMessage.decode(result)
            print(x.content)


if __name__ == "__main__":
    set_stderr_logger()
    asyncio.run(main())
