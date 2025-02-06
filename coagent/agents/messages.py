from __future__ import annotations

from typing import Any, Type

from coagent.core import logger, Message
from pydantic import BaseModel, Field, field_validator, field_serializer


class ChatMessage(Message):
    role: str = Field(
        ..., description="The role of the message. (e.g. `user`, `assistant`)"
    )
    content: str = Field(
        default="",
        description="The content of the message. For reasoning models, this is the content of the final answer.",
    )
    reasoning_content: str = Field(
        default="",
        description="The content of the CoT. Only available for reasoning models.",
    )

    type: str = Field(default="", description="The type of the message. e.g. confirm")
    sender: str = Field(default="", description="The sending agent of the message.")
    to_user: bool = Field(
        default=False, description="Whether the message is sent directly to user."
    )

    def __add__(self, other: ChatMessage) -> ChatMessage:
        self.content += other.content
        self.reasoning_content += other.reasoning_content
        return self

    @property
    def has_content(self) -> bool:
        return bool(self.content or self.reasoning_content)

    def model_dump(self, **kwargs) -> dict[str, Any]:
        return super().model_dump(include={"role", "content"}, **kwargs)

    def to_llm_message(self) -> dict[str, Any]:
        return super().model_dump(include={"role", "content"})


class ChatHistory(Message):
    messages: list[ChatMessage]


class StructuredOutput(Message):
    input: ChatMessage | ChatHistory = Field(..., description="Input message.")
    output_type: Type[BaseModel] | None = Field(
        None,
        description="Output schema specified as a Pydantic model. Equivalent to OpenAI's `response_format`.",
    )
    output_schema: dict | None = Field(
        None,
        description="Output schema specified as a dict. Setting this suppresses `output_type`.",
    )

    @field_serializer("input")
    def serialize_input(self, value: Message, _info) -> dict:
        data = value.model_dump(exclude_defaults=True)
        data["__message_type__"] = value.__class__.__name__
        return data

    @field_validator("input", mode="before")
    @classmethod
    def validate_input(cls, value: Message | dict) -> Message:
        if isinstance(value, dict):
            message_type = value.pop("__message_type__", None)
            match message_type:
                # Only support ChatMessage and ChatHistory for now.
                case "ChatMessage":
                    return ChatMessage.model_validate(value)
                case "ChatHistory":
                    return ChatHistory.model_validate(value)
        return value

    @field_serializer("output_type")
    def serialize_output_type(self, value: Type[BaseModel] | None, _info) -> None:
        # Always return None for `output_type` since it will be converted to `output_schema`.
        return None

    @field_serializer("output_schema")
    def serialize_output_schema(self, value: dict | None, _info) -> dict | None:
        if self.output_type:
            if value:
                logger.warning("Setting output_schema suppresses output_type")
                return value
            return type_to_response_format_param(self.output_type)

        return value


def type_to_response_format_param(
    response_format: Type[BaseModel] | dict | None,
) -> dict | None:
    import litellm.utils

    return litellm.utils.type_to_response_format_param(response_format)
