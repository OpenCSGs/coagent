from __future__ import annotations

import abc
import dataclasses
import enum
from typing import Any, AsyncIterator, Awaitable, Callable, Type
import uuid

from pydantic import BaseModel, Field


# Mapping from singleton agent type to coagent topic.
agent_types_to_topics = {
    "discovery": "coagent.discovery",
    "discovery.server": "coagent.discovery.server",
}
# Mapping from coagent topic to singleton agent type.
topics_to_agent_types = {v: k for k, v in agent_types_to_topics.items()}

coagent_factory_topic_prefix = "coagent.factory."
coagent_agent_topic_prefix = "coagent.agent."
coagent_reply_topic_prefix = (
    "_INBOX."  # Actually this is the reply topic prefix of NATS.
)


class Address(BaseModel):
    name: str = Field(description="Agent type")
    id: str = Field(default="", description="Session ID")

    def __hash__(self):
        return hash(self.topic)

    def __eq__(self, other: Address | None):
        if other is None:
            return False
        return self.topic == other.topic

    @property
    def is_reply(self) -> bool:
        return self.name.startswith(coagent_reply_topic_prefix)

    @property
    def topic(self) -> str:
        # For a singleton agent.
        _topic = agent_types_to_topics.get(self.name)
        if _topic:
            return _topic

        if self.is_reply:
            return self.name

        if self.id:
            # Normal agent.
            return f"{coagent_agent_topic_prefix}{self.name}.{self.id}"
        else:
            # Factory agent.
            return f"{coagent_factory_topic_prefix}{self.name}"

    @classmethod
    def from_topic(cls, topic: str) -> Address:
        # For a singleton agent.
        agent_type = topics_to_agent_types.get(topic)
        if agent_type:
            return cls(name=agent_type)

        if topic.startswith(coagent_reply_topic_prefix):
            return cls(name=topic)

        if topic.startswith(coagent_agent_topic_prefix):
            relative_topic = topic.removeprefix(coagent_agent_topic_prefix)
        elif topic.startswith(coagent_factory_topic_prefix):
            relative_topic = topic.removeprefix(coagent_factory_topic_prefix)
        else:
            raise ValueError(f"Invalid topic: {topic}")

        words = relative_topic.split(".", 1)
        if len(words) == 1:
            return cls(name=words[0])
        else:  # len(words) == 2
            return cls(name=words[0], id=words[1])

    def encode(self, mode: str = "python") -> dict:
        return self.model_dump(mode=mode)

    @classmethod
    def decode(cls, data: dict) -> Address:
        return cls.model_validate(data)


class Reply(BaseModel):
    address: Address = Field(..., description="Reply address.")
    stream: bool = Field(
        False, description="Whether the sender requests a streaming result."
    )


# A sentinel reply object that indicates no reply will be sent.
#
# This is mainly used by the orchestration agents who delegate the reply
# handling to other agents.
NO_REPLY = Reply(address=Address(name="", id=""), stream=False)


class MessageHeader(BaseModel):
    type: str = Field(..., description="Message type name.")
    content_type: str = Field(
        default="application/json", description="Message content type."
    )
    extensions: dict = Field(default_factory=dict, description="Extension fields.")


class RawMessage(BaseModel):
    header: MessageHeader = Field(..., description="Message header.")
    reply: Reply | None = Field(default=None, description="Reply information.")
    content: bytes = Field(default=b"", description="Message content.")

    def encode(self, mode: str = "python", exclude_defaults: bool = True) -> dict:
        return self.model_dump(mode=mode, exclude_defaults=exclude_defaults)

    @classmethod
    def decode(cls, data: dict) -> RawMessage:
        return cls.model_validate(data)

    def encode_json(self, exclude_defaults: bool = True) -> str:
        return self.model_dump_json(exclude_defaults=exclude_defaults)

    @classmethod
    def decode_json(cls, json_data: str | bytes) -> RawMessage:
        return cls.model_validate_json(json_data)


class Constructor:
    def __init__(self, typ: Type, *args: Any, **kwargs: Any) -> None:
        self.type: Type = typ
        self.args: tuple[Any] = args
        self.kwargs: dict[str, Any] = kwargs

        # When a `__post_call__()` method is defined on the class, it will be
        # called by `__call__()`, normally as `self.__post_call__(agent)`.
        self._post_call_fn: Callable[[Agent], Awaitable[None]] | None = getattr(
            self, "__post_call__", None
        )

    async def __call__(
        self, channel: Channel, address: Address, factory_address: Address | None = None
    ) -> Agent:
        agent = self.type(*self.args, **self.kwargs)
        agent.init(channel, address, factory_address)

        if self._post_call_fn is not None:
            await self._post_call_fn(agent)

        return agent


# new is a shortcut for Constructor.
new = Constructor


class State(str, enum.Enum):
    STARTED = "started"
    RUNNING = "running"
    IDLE = "idle"  # Only this state is actually used for now.
    STOPPED = "stopped"


class Agent(abc.ABC):
    @property
    @abc.abstractmethod
    def id(self) -> str:
        """Return the unique ID of the agent."""
        pass

    @abc.abstractmethod
    def init(
        self, channel: Channel, address: Address, factory_address: Address | None = None
    ) -> None:
        """Initialize the agent with the given channel and address."""
        pass

    @abc.abstractmethod
    async def get_state(self) -> State:
        """Get the current state of the agent."""
        pass

    @abc.abstractmethod
    async def start(self) -> None:
        """Start the current agent."""
        pass

    @abc.abstractmethod
    async def stop(self) -> None:
        """Stop the current agent."""
        pass

    @abc.abstractmethod
    async def delete(self) -> None:
        """Request to delete the current agent."""
        pass

    @abc.abstractmethod
    async def started(self) -> None:
        """This handler is called after the agent is started."""
        pass

    @abc.abstractmethod
    async def stopped(self) -> None:
        """This handler is called after the agent is stopped."""
        pass

    @abc.abstractmethod
    async def receive(self, raw: RawMessage) -> None:
        """Handle the incoming raw message."""
        pass


class Subscription(abc.ABC):
    @abc.abstractmethod
    async def unsubscribe(self, limit: int = 0) -> None:
        """Align to NATS for simplicity."""
        pass


class Channel(abc.ABC):
    @abc.abstractmethod
    async def connect(self) -> None:
        pass

    @abc.abstractmethod
    async def close(self) -> None:
        pass

    @abc.abstractmethod
    async def publish(
        self,
        addr: Address,
        msg: RawMessage,
        stream: bool = False,
        request: bool = False,
        reply: str = "",
        timeout: float = 0.5,
        probe: bool = True,
    ) -> AsyncIterator[RawMessage] | RawMessage | None:
        """Publish a message to the given address.

        Args:
            addr (Address): The address of the agent.
            msg (RawMessage): The raw message to send.
            stream (bool, optional): Whether to request a streaming result. Defaults to False.
            request (bool, optional): Whether this is a request. Defaults to False. If `stream` is True, then this is always True.
            reply (str, optional): If `request` is True, then this will be the subject to reply to. Defaults to "".
            timeout (float, optional): If `request` is True, then this will be the timeout for the response. Defaults to 0.5.
            probe (bool, optional): Whether to probe the agent before sending the message. Defaults to True.
        """
        pass

    @abc.abstractmethod
    async def subscribe(
        self,
        addr: Address,
        handler: Callable[[RawMessage], Awaitable[None]],
        queue: str = "",
    ) -> Subscription:
        pass

    @abc.abstractmethod
    async def new_reply_topic(self) -> str:
        pass

    @abc.abstractmethod
    async def cancel(self, addr: Address) -> None:
        """Cancel the agent with the given address."""
        pass


@dataclasses.dataclass
class AgentSpec:
    """The specification of an agent."""

    name: str
    constructor: Constructor
    description: str = ""

    __runtime: Runtime | None = dataclasses.field(default=None, init=False)

    def register(self, runtime: Runtime) -> None:
        """Register the agent specification to a runtime."""
        self.__runtime = runtime

    async def run(
        self,
        msg: RawMessage,
        stream: bool = False,
        session_id: str = "",
        timeout: float = 0.5,
    ) -> AsyncIterator[RawMessage] | RawMessage | None:
        """Create an agent and run it with the given message."""
        if self.__runtime is None:
            raise ValueError(f"AgentSpec {self.name} is not registered to a runtime.")

        session_id = session_id or uuid.uuid4().hex
        addr = Address(name=self.name, id=session_id)

        return await self.__runtime.channel.publish(
            addr, msg, stream=stream, request=True, timeout=timeout
        )


class Runtime(abc.ABC):
    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()

    @abc.abstractmethod
    async def start(self) -> None:
        pass

    @abc.abstractmethod
    async def stop(self) -> None:
        pass

    @abc.abstractmethod
    async def register(self, spec: AgentSpec) -> None:
        pass

    @abc.abstractmethod
    async def deregister(self, *names: str) -> None:
        pass

    @property
    @abc.abstractmethod
    def channel(self) -> Channel:
        pass
