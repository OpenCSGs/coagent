from __future__ import annotations

import json
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .types import MessageHeader, RawMessage, Reply


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: Reply | None = Field(default=None, description="Reply information.")
    extensions: dict = Field(
        default_factory=dict, description="Extension fields from RawMessage header."
    )

    def __add__(self, other: Message) -> Message:
        """Concatenate two messages.

        This binary operator is mainly used to aggregate multiple streaming
        messages into one message when the sender requests to receive a
        non-streaming result.
        """
        return NotImplemented

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


class ControlMessage(Message):
    """ControlMessage is the base class for all control messages.

    A control message is used to control the behavior of an agent. For example,
    a `Cancel` message can be sent to an agent to cancel the processing of the
    agent and delete it.

    For a specific agent, CONTROL messages and DATA messages are processed in
    separate coroutines, so CONTROL messages can be processed in a timely manner
    without being blocked by DATA messages. By design, CONTROL messages are
    management commands that must be processed instantly and do not wait for
    any return value.

    Any CONTROL message should be a subclass of this class. And any other messages,
    inherited from `Message`, are DATA messages.
    """

    pass


class Cancel(ControlMessage):
    """A control message to cancel the processing of an agent and delete it."""

    pass


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


class SetReplyInfo(Message):
    """A message to set the reply information of an agent.

    This is mainly useful when orchestrating multiple agents to work together.
    """

    reply_info: Reply


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
