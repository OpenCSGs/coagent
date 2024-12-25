import asyncio
import time
from typing import Any, AsyncIterator, Callable, Type, get_type_hints, cast

from pydantic import BaseModel, ValidationError

from .exceptions import MessageDecodeError, InternalError
from .logger import logger
from .messages import (
    Message,
    Started,
    Stopped,
    SetReplyAgent,
    ProbeAgent,
    Empty,
    StopIteration,
)
from .types import Address, Agent, Channel, RawMessage, State, Subscription


class Context:
    pass


def get_type_name(typ: Type[Any]) -> str:
    return f"{typ.__module__}.{typ.__qualname__}"


def handler(func):
    """Decorator to mark the given function as a message handler.

    This decorator is typically used on methods of an agent class, and the method must have 3 arguments:
        1. `self`
        2. `msg`: The message to be handled, this must be type-hinted with the message type that it is intended to handle.
        3. `ctx`: A Context object.
    """
    hints = get_type_hints(func)
    return_type = hints.pop("return", None)  # Ignore the return type.
    if len(hints) != 2:
        raise AssertionError(
            "The handler method must have 3 arguments: (self, msg, ctx)"
        )

    params = list(hints.items())
    msg_name, msg_type = params[0]
    ctx_name, ctx_type = params[1]

    if not issubclass(msg_type, Message):
        want, got = get_type_name(Message), get_type_name(msg_type)
        raise AssertionError(
            f"The argument '{msg_name}' must be type-hinted with a subclass of `{want}` type (got `{got}`)"
        )

    if ctx_type is not Context:
        want, got = get_type_name(Context), get_type_name(ctx_type)
        raise AssertionError(
            f"The argument '{ctx_name}' must be type-hinted with a `{want}` type (got `{got}`)"
        )

    func.is_message_handler = True
    func.target_message_type = msg_type
    func.return_type = get_return_type(return_type)
    return func


def get_return_type(typ: Type[Any]) -> Type[Any]:
    if hasattr(typ, "__origin__") and issubclass(typ.__origin__, AsyncIterator):
        if hasattr(typ, "__args__"):
            # Extract the inner type T from `AsyncIterator[T]`.
            return typ.__args__[0]

    return typ


Handler = Callable[[Any, Any, Any], Any]


class Operation(BaseModel):
    """Operation represents a message handler of the corresponding agent."""

    name: str
    description: str
    message: dict
    reply: dict


class BaseAgent(Agent):
    """BaseAgent is the base class for all agents.

    Args:
        timeout (float, optional): The inactivity timeout for transitioning the
            agent state from RUNNING to IDLE. Defaults to 60 (in seconds).

            If the agent is not receiving any messages within this duration, it
            will be transitioned to the IDLE state. Once in the IDLE state, the
            agent will be deleted (recycled) by its corresponding factory agent.
    """

    def __init__(self, timeout: float = 60):
        # Note that channel and address will be set by the runtime after agent creation.
        self.channel: Channel | None = None
        self.address: Address | None = None

        self._sub: Subscription | None = None

        self._timeout: float = timeout
        self._last_msg_received_at: float = time.time()

        # A lock to protect the access to `self._last_msg_received_at`, which
        # will be written to when receiving messages and read from when getting
        # the state of this agent.
        #
        # Note that it's possible to avoid using locks if the factory agent
        # gets the state of this agent through sending query messages, but
        # this would result in a lot of messages.
        self._lock: asyncio.Lock = asyncio.Lock()

        # Normally reply_address is set by an orchestration agent by sending a `SetReplyAgent` message.
        self.reply_address: Address | None = None

        handlers, message_types = self.__collect_handlers()
        # A list of handlers that are registered to handle messages.
        self._handlers: dict[Type, Handler] = handlers
        # A list of message types associated with this agent.
        self._message_types: dict[str, Type[Message]] = {
            "Started": Started,
            "Stopped": Stopped,
            "SetReplyAgent": SetReplyAgent,
            "ProbeAgent": ProbeAgent,
            "Empty": Empty,
            **message_types,
        }

    def init(self, channel: Channel, address: Address) -> None:
        self.channel = channel
        self.address = address

    async def get_state(self) -> State:
        async with self._lock:
            elapsed = time.time() - self._last_msg_received_at

        if elapsed >= self._timeout:
            return State.IDLE
        return State.RUNNING

    async def start(self) -> None:
        """Start the current agent."""

        # Subscribe the agent to its own address.
        self._sub = await self.channel.subscribe(self.address, handler=self.receive)

        # Send a `Started` message to the current agent.
        await self.channel.publish(self.address, Started().encode(), probe=False)

    async def stop(self) -> None:
        """Stop the current agent."""

        # Send a `Stopped` message to the current agent.
        await self.channel.publish(self.address, Stopped().encode(), probe=False)

        # Unsubscribe the agent from its own address.
        if self._sub:
            await self._sub.unsubscribe()

    async def started(self) -> None:
        """This handler is called after the agent is started."""
        pass

    async def stopped(self) -> None:
        """This handler is called after the agent is stopped."""
        pass

    async def receive(self, raw: RawMessage) -> None:
        logger.debug(
            f"[{self.__class__.__name__}] Received a message: {raw.model_dump()}"
        )

        async with self._lock:
            self._last_msg_received_at = time.time()

        msg_type_name = raw.header.type
        msg_type = self._message_types.get(msg_type_name)
        if not msg_type:
            # If the message type is not found, try to use the generic message.
            msg_type = self._message_types.get("GenericMessage")
            if not msg_type:
                err = MessageDecodeError(f"message type '{msg_type_name}' not found")
                sent = await self.__send_reply(raw.reply, err.encode_message())
                if not sent:
                    logger.error(f"Failed to decode message: {err}")
                return

        try:
            msg = msg_type.decode(raw)
        except ValidationError as exc:
            err = MessageDecodeError(str(exc))
            sent = await self.__send_reply(raw.reply, err.encode_message())
            if not sent:
                logger.error(f"Failed to decode message: {err}")
            return

        match msg:
            case Started():
                await self.started()

            case Stopped():
                await self.stopped()

            case SetReplyAgent():
                self.reply_address = msg.address

            case ProbeAgent() | Empty():
                # Do not handle probes and empty messages.
                pass

            case _:
                await self._handle(msg, Context())

    async def _handle(self, msg: Message, ctx: Context) -> None:
        h: Handler = self.__get_handler(msg)
        result = h(self, msg, ctx)

        async def pub(x: Message):
            await self.__send_reply(msg.reply, x)

        if is_async_iterator(result):
            try:
                async for x in result:
                    await pub(x)
            except Exception as exc:
                err = InternalError.from_exception(exc)
                await pub(err.encode_message())
            # End of the iteration, send an extra StopIteration message.
            await pub(StopIteration())
        else:
            try:
                x = await result or Empty()
            except Exception as exc:
                err = InternalError.from_exception(exc)
                x = err.encode_message()
            await pub(x)

    async def __send_reply(self, in_msg_reply: Address, out_msg: Message) -> bool:
        reply_address = self.reply_address or in_msg_reply
        if not reply_address:
            return False

        # Reply to the sending agent if asked.
        await self.channel.publish(reply_address, out_msg.encode())
        return True

    def __get_handler(self, msg: Message) -> Handler | None:
        msg_type: Type[Any] = type(msg)

        # Try to find a handler specific to the exact message type.
        h = self._handlers.get(msg_type)
        if not h:
            # Use the handler for all messages, if there is one.
            h = self._handlers.get(Message)

        return h

    @classmethod
    def __collect_handlers(cls) -> tuple[dict[Type, Handler], dict[str, Type[Message]]]:
        handlers: dict[Type, Handler] = {}
        message_types: dict[str, Type[Message]] = {}
        for attr in dir(cls):
            if callable(getattr(cls, attr, None)):
                h = getattr(cls, attr)
                if hasattr(h, "is_message_handler"):
                    handlers[h.target_message_type] = cast(Handler, h)
                    message_types[h.target_message_type.__name__] = (
                        h.target_message_type
                    )
                    if h.return_type:
                        message_types[h.return_type.__name__] = h.return_type
        return handlers, message_types

    @classmethod
    def collect_operations(cls) -> list[Operation]:
        handlers: dict[Type, Handler] = cls.__collect_handlers()[0]
        operations = []
        for h in handlers.values():
            operations.append(
                Operation(
                    name=h.__name__,
                    description=h.__doc__ or h.__name__,
                    message=h.target_message_type.model_json_schema(),
                    reply=h.return_type.model_json_schema()
                    if h.return_type is not type(None)
                    else {},
                )
            )
        return operations


def is_async_iterator(obj) -> bool:
    """Check if obj is an async-iterator."""
    return hasattr(obj, "__aiter__") and hasattr(obj, "__anext__")
