import asyncio
import os

from coagent.agents import ChatMessage, DynamicTriage, ModelClient, StreamChatAgent
from coagent.core import AgentSpec, new, set_stderr_logger
from coagent.runtimes import LocalRuntime

client = ModelClient(
    model=os.getenv("MODEL_NAME"),
    api_base=os.getenv("MODEL_API_BASE"),
    api_version=os.getenv("MODEL_API_VERSION"),
    api_key=os.getenv("MODEL_API_KEY"),
)

billing = AgentSpec(
    "team.billing",  # Under the team namespace
    new(
        StreamChatAgent,
        system="""\
You are a billing support specialist. Follow these guidelines:
1. Always start with "Billing Support Response:"
2. First acknowledge the specific billing issue
3. Explain any charges or discrepancies clearly
4. List concrete next steps with timeline
5. End with payment options if relevant

Keep responses professional but friendly.\
""",
        client=client,
    ),
)

technical = AgentSpec(
    "team.technical",  # Under the team namespace
    new(
        StreamChatAgent,
        system="""\
You are a technical support engineer. Follow these guidelines:
1. Always start with "Technical Support Response:"
2. List exact steps to resolve the issue
3. Include system requirements if relevant
4. Provide workarounds for common problems
5. End with escalation path if needed

Use clear, numbered steps and technical details.\
""",
        client=client,
    ),
)

account = AgentSpec(
    "team.account",  # Under the team namespace
    new(
        StreamChatAgent,
        system="""\
You are an account security specialist. Follow these guidelines:
1. Always start with "Account Support Response:"
2. Prioritize account security and verification
3. Provide clear steps for account recovery/changes
4. Include security tips and warnings
5. Set clear expectations for resolution time

Maintain a serious, security-focused tone.\
""",
        client=client,
    ),
)

triage = AgentSpec(
    "triage",
    new(
        DynamicTriage,
        system="""You are a triage agent who will delegate to sub-agents based on the conversation content.""",
        client=client,
        namespace="team",  # Collect all sub-agents under the team namespace
    ),
)


async def main():
    async with LocalRuntime() as runtime:
        for spec in [billing, technical, account, triage]:
            await runtime.register_spec(spec)

        result = triage.run_stream(
            ChatMessage(
                role="user",
                content="""\
Subject: Can't access my account
Message: Hi, I've been trying to log in for the past hour but keep getting an 'invalid password' error. 
I'm sure I'm using the right password. Can you help me regain access? This is urgent as I need to 
submit a report by end of day.
- John\
""",
            ).encode()
        )
        async for chunk in result:
            msg = ChatMessage.decode(chunk)
            print(msg.content, end="", flush=True)


if __name__ == "__main__":
    set_stderr_logger("TRACE")
    asyncio.run(main())
