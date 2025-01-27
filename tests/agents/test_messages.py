from pydantic import BaseModel, ValidationError
import pytest

from coagent.agents import ChatHistory, ChatMessage, StructuredOutput


class FriendInfo(BaseModel):
    name: str
    age: int
    is_available: bool


want_output_schema = {
    "json_schema": {
        "name": "FriendInfo",
        "schema": {
            "additionalProperties": False,
            "properties": {
                "age": {
                    "title": "Age",
                    "type": "integer",
                },
                "is_available": {
                    "title": "Is Available",
                    "type": "boolean",
                },
                "name": {
                    "title": "Name",
                    "type": "string",
                },
            },
            "required": [
                "name",
                "age",
                "is_available",
            ],
            "title": "FriendInfo",
            "type": "object",
        },
        "strict": True,
    },
    "type": "json_schema",
}


class TestStructuredOutput:
    @pytest.mark.asyncio
    async def test_chat_message(self):
        # Test model_dump
        output = StructuredOutput(
            input=ChatMessage(role="user", content="I have a friend."),
            output_type=FriendInfo,
        )
        want_output_dict = {
            "input": {
                "__message_type__": "ChatMessage",
                "content": "I have a friend.",
                "role": "user",
            },
            "output_schema": want_output_schema,
            "output_type": None,
        }
        assert output.model_dump(exclude_defaults=True) == want_output_dict

        # Test model_validate
        output2 = StructuredOutput.model_validate(want_output_dict)
        assert isinstance(output2.input, ChatMessage)
        assert output2.input.role == "user"
        assert output2.input.content == "I have a friend."

    @pytest.mark.asyncio
    async def test_chat_history(self):
        # Test model_dump
        output = StructuredOutput(
            input=ChatHistory(
                messages=[ChatMessage(role="user", content="I have a friend.")]
            ),
            output_type=FriendInfo,
        )
        want_output_dict = {
            "input": {
                "__message_type__": "ChatHistory",
                "messages": [
                    {
                        "content": "I have a friend.",
                        "role": "user",
                    }
                ],
            },
            "output_schema": want_output_schema,
            "output_type": None,
        }
        assert output.model_dump(exclude_defaults=True) == want_output_dict

        # Test model_validate
        output2 = StructuredOutput.model_validate(want_output_dict)
        assert isinstance(output2.input, ChatHistory)
        assert output2.input.messages[0].role == "user"
        assert output2.input.messages[0].content == "I have a friend."

    @pytest.mark.asyncio
    async def test_invalid_input(self):
        class InvalidInput(BaseModel):
            pass

        with pytest.raises(ValidationError) as exc:
            _ = StructuredOutput(
                input=InvalidInput(),
                output_type=FriendInfo,
            )

        exc_value = str(exc.value)
        assert "2 validation errors for StructuredOutput" in exc_value
        assert (
            "Input should be a valid dictionary or instance of ChatMessage" in exc_value
        )
        assert (
            "Input should be a valid dictionary or instance of ChatHistory" in exc_value
        )
