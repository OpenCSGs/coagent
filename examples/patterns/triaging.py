import asyncio
import os

from coagent.agents import ChatAgent, ChatMessage, Triage, Model
from coagent.core import AgentSpec, new, init_logger
from coagent.runtimes import LocalRuntime

model = Model(
    id=os.getenv("MODEL_ID"),
    base_url=os.getenv("MODEL_BASE_URL"),
    api_version=os.getenv("MODEL_API_VERSION"),
    api_key=os.getenv("MODEL_API_KEY"),
)

billing = AgentSpec(
    "billing",
    new(
        ChatAgent,
        system="""\
You are a billing support specialist. Follow these guidelines:
1. Always start with "Billing Support Response:"
2. First acknowledge the specific billing issue
3. Explain any charges or discrepancies clearly
4. List concrete next steps with timeline
5. End with payment options if relevant

Keep responses professional but friendly.\
""",
        model=model,
    ),
)

account = AgentSpec(
    "account",
    new(
        ChatAgent,
        system="""\
You are an account security specialist. Follow these guidelines:
1. Always start with "Account Support Response:"
2. Prioritize account security and verification
3. Provide clear steps for account recovery/changes
4. Include security tips and warnings
5. Set clear expectations for resolution time

Maintain a serious, security-focused tone.\
""",
        model=model,
    ),
)

triage = AgentSpec(
    "triage",
    new(
        Triage,
        system="""You are a triage agent who will delegate to sub-agents based on the conversation content.""",
        model=model,
        static_agents=["billing", "account"],
    ),
)


async def main():
    async with LocalRuntime() as runtime:
        for spec in [billing, account, triage]:
            await runtime.register(spec)

        result = await triage.run(
            ChatMessage(
                role="user",
                content="""\
Subject: Can't access my account
Message: Hi, I've been trying to log in for the past hour but keep getting an 'invalid password' error. 
I'm sure I'm using the right password. Can you help me regain access? This is urgent as I need to 
submit a report by end of day.
- John\
""",
            ).encode(),
            stream=True,
        )
        async for chunk in result:
            msg = ChatMessage.decode(chunk)
            print(msg.content, end="", flush=True)


if __name__ == "__main__":
    init_logger()
    asyncio.run(main())
