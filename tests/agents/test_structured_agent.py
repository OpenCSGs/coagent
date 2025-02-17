from typing import AsyncIterator

from coagent.agents import ChatHistory, ChatMessage
from coagent.agents.structured_agent import StructuredAgent
from coagent.core import Context, GenericMessage, Message
from pydantic import BaseModel
import pytest


class Input(Message):
    role: str = ""
    content: str = ""


class Output(BaseModel):
    content: str = ""


class MockAgent(StructuredAgent):
    async def _handle_history(
        self,
        msg: ChatHistory,
        response_format: dict | None = None,
    ) -> AsyncIterator[ChatMessage]:
        if response_format and response_format["json_schema"]["name"] == "Output":
            out = Output(content="Hello!")
            yield ChatMessage(role="assistant", content=out.model_dump_json())
        else:
            yield ChatMessage(role="assistant", content="Hello!")


class TestStructuredAgent:
    @pytest.mark.asyncio
    async def test_render_system(self):
        agent = StructuredAgent(
            input_type=Input, system="You are a helpful {{ role }}."
        )

        system = await agent.render_system(Input(role="Translator"))
        assert system == "You are a helpful Translator."

    @pytest.mark.asyncio
    async def test_render_messages(self):
        agent = StructuredAgent(
            input_type=Input,
            messages=[ChatMessage(role="user", content="{{ content }}")],
        )

        messages = await agent.render_messages(Input(content="Hello"))
        assert messages == [ChatMessage(role="user", content="Hello")]

    @pytest.mark.asyncio
    async def test_handle_input(self):
        agent = MockAgent(
            input_type=Input,
        )

        # Success
        _input = GenericMessage.decode(Input().encode())
        async for msg in agent.handle(_input, Context()):
            assert msg.content == "Hello!"

        # Error
        _input = GenericMessage.decode(ChatMessage(role="").encode())
        with pytest.raises(ValueError) as exc:
            async for _ in agent.handle(_input, Context()):
                pass
        assert "Invalid message type" in str(exc.value)

    @pytest.mark.asyncio
    async def test_handle_output(self):
        agent = MockAgent(
            input_type=Input,
            output_type=Output,
        )

        _input = GenericMessage.decode(Input().encode())
        async for msg in agent.handle(_input, Context()):
            assert msg.content == '{"content":"Hello!"}'
