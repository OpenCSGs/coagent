from __future__ import annotations

from typing import Any

from pydantic import Field
from coagent.core import Message


class ChatMessage(Message):
    role: str
    content: str
    response_format: dict | None = None

    type: str = Field(default="", description="The type of the message. e.g. confirm")
    sender: str = Field(default="", description="The sending agent of the message.")
    to_user: bool = Field(
        default=False, description="Whether the message is sent directly to user."
    )

    def __add__(self, other: ChatMessage) -> ChatMessage:
        self.content += other.content
        return self

    def model_dump(self, **kwargs) -> dict[str, Any]:
        return super().model_dump(include={"role", "content"}, **kwargs)

    def to_llm_message(self) -> dict[str, Any]:
        return super().model_dump(include={"role", "content"})


class ChatHistory(Message):
    messages: list[ChatMessage]
    response_format: dict | None = None
