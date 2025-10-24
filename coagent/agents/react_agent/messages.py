from coagent.core import Message
from pydantic import Field
from typing import Literal

from .types import (
    MessageOutputItem,
    ToolCallItem,
    ToolCallOutputItem,
    ToolCallProgressItem,
)


class InputMessage(Message):
    role: Literal["user", "assistant"] = Field(
        ..., description="The role of the message. (e.g. `user`, `assistant`)"
    )
    content: str = Field(
        ...,
        description="The content of the message.",
    )


class InputHistory(Message):
    messages: list[InputMessage] = Field(..., description="A list of input messages.")


class OutputMessage(Message):
    item: (
        MessageOutputItem | ToolCallItem | ToolCallOutputItem | ToolCallProgressItem
    ) = Field(..., description="The event item.")
