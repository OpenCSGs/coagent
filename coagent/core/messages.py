from __future__ import annotations

import json
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .types import Address, MessageHeader, RawMessage


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: Address | None = Field(default=None, description="Reply address.")
    extensions: dict = Field(
        default_factory=dict, description="Extension fields from RawMessage header."
    )

    def encode(
        self, content_type: str = "application/json", exclude_defaults: bool = True
    ) -> RawMessage:
        if not content_type == "application/json":
            raise ValidationError.from_exception_data("Invalid content type", [])

        content = self.model_dump_json(
            exclude={"reply", "extensions"},
            exclude_defaults=exclude_defaults,
        )
        if content == "{}":
            content = ""

        return RawMessage(
            header=MessageHeader(
                type=self.__class__.__name__,
                content_type=content_type,
                extensions=self.extensions,
            ),
            content=content.encode("utf-8"),
        )

    @classmethod
    def decode(cls, raw: RawMessage) -> Message:
        if raw.header.type != cls.__name__:
            raise ValidationError.from_exception_data("Invalid message type", [])

        if not raw.header.content_type == "application/json":
            raise ValidationError.from_exception_data("Invalid content type", [])

        data = {"reply": raw.reply, "extensions": raw.header.extensions}
        if raw.content:
            try:
                data.update(json.loads(raw.content.decode("utf-8")))
            except json.JSONDecodeError as exc:
                raise ValidationError.from_exception_data(str(exc), [])

        return cls.model_validate(data)


class GenericMessage(Message):
    """A generic message that can be used for any type of message."""

    raw: RawMessage = Field(..., description="The raw message.")

    def encode(
        self, content_type: str = "application/json", exclude_defaults: bool = True
    ) -> RawMessage:
        return self.raw

    @classmethod
    def decode(cls, raw: RawMessage) -> Message:
        return cls(reply=raw.reply, extensions=raw.header.extensions, raw=raw)


class Started(Message):
    """A message to notify an agent that it's started."""

    pass


class Stopped(Message):
    """A message to notify an agent that it's stopped."""

    pass


class ProbeAgent(Message):
    """A message to probe the existence of an agent."""

    pass


class SetReplyAgent(Message):
    """A message to set the agent to reply to."""

    address: Address


class Empty(Message):
    """A message that serves as a placeholder."""

    pass


class StopIteration(Message):
    """A message to notify the end of an iteration."""

    pass


class Error(Message):
    """A message to notify an error."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
