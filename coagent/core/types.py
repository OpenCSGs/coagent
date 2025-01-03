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


class MessageHeader(BaseModel):
    type: str = Field(..., description="Message type name.")
    content_type: str = Field(
        default="application/json", description="Message content type."
    )
    extensions: dict = Field(default_factory=dict, description="Extension fields.")


class RawMessage(BaseModel):
    header: MessageHeader = Field(..., description="Message header.")
    reply: Address | None = Field(default=None, description="Reply address.")
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
        self.type = typ
        self.args = args
        self.kwargs = kwargs

    async def __call__(self, channel: Channel, address: Address) -> Agent:
        agent = self.type(*self.args, **self.kwargs)
        agent.init(channel, address)
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
    def init(self, channel: Channel, address: Address) -> None:
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
        request: bool = False,
        reply: str = "",
        timeout: float = 0.5,
        probe: bool = True,
    ) -> RawMessage | None:
        """Publish a message.

        Args:
            addr (Address): The address of the agent.
            msg (RawMessage): The raw message to send.
            request (bool, optional): Whether this is a request. Defaults to False.
            reply (str, optional): If `request` is True, then this will be the subject to reply to. Defaults to "".
            timeout (float, optional): If `request` is True, then this will be the timeout for the response. Defaults to 0.5.
            probe (bool, optional): Whether to probe the agent before sending the message. Defaults to True.
        """
        pass

    @abc.abstractmethod
    async def publish_multi(
        self,
        addr: Address,
        msg: RawMessage,
        probe: bool = True,
    ) -> AsyncIterator[RawMessage]:
        """Publish a message and wait for multiple reply messages.

        Args:
            addr (Address): The address of the agent.
            msg (RawMessage): The raw message to send.
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

    async def run(self, msg: RawMessage, timeout: float = 0.5) -> RawMessage:
        """Create an agent and run it with the given message."""
        self.__assert_runtime()

        addr = Address(name=self.name, id=uuid.uuid4().hex)
        return await self.__runtime.channel.publish(
            addr, msg, request=True, timeout=timeout
        )

    async def run_stream(self, msg: RawMessage) -> AsyncIterator[RawMessage]:
        """Create an agent and run it with the given message."""
        self.__assert_runtime()

        addr = Address(name=self.name, id=uuid.uuid4().hex)
        result = self.__runtime.channel.publish_multi(addr, msg)
        async for chunk in result:
            yield chunk

    def __assert_runtime(self) -> None:
        if self.__runtime is None:
            raise ValueError(f"AgentSpec {self.name} is not registered to a runtime.")


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

    async def register(
        self, name: str, constructor: Constructor, description: str = ""
    ) -> None:
        await self.register_spec(
            AgentSpec(name=name, constructor=constructor, description=description)
        )

    @abc.abstractmethod
    async def register_spec(self, spec: AgentSpec) -> None:
        pass

    @abc.abstractmethod
    async def deregister(self, *names: str) -> None:
        pass

    @property
    @abc.abstractmethod
    def channel(self) -> Channel:
        pass
