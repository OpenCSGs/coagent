from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, AsyncIterator, Awaitable, Callable, Type, get_type_hints, cast

from pydantic import BaseModel, ValidationError

from .exceptions import MessageDecodeError, InternalError, StreamError
from .logger import logger
from .messages import (
    Cancel,
    ControlMessage,
    Empty,
    ProbeAgent,
    Message,
    Started,
    Stopped,
    SetReplyInfo,
    StopIteration,
)
from .types import (
    Address,
    Agent,
    Channel,
    RawMessage,
    Reply,
    State,
    Subscription,
)


class Context:
    pass


def get_type_name(typ: Type[Any]) -> str:
    return f"{typ.__module__}.{typ.__qualname__}"


def handler(func: Callable | None = None, deferred: bool = False) -> Callable:
    """Decorator to mark the given function as a message handler.

    This decorator is typically used on methods of an agent class, and the method must have 3 arguments:
        1. `self`
        2. `msg`: The message to be handled, this must be type-hinted with the message type that it is intended to handle.
        3. `ctx`: A Context object.

    Args:
        func: The function to be decorated.
        deferred: Whether the reply from the decorated message handler will be deferred.

            This is mainly used by message handlers that want to send a reply
            in a different way, rather than directly returning it.

            Example scenarios:
            - Message handlers of orchestration agents who delegate the reply handling to other agents.
            - Message handlers that process blocking tasks in a separate coroutine and send replies there.
    """

    def decorator(func: Callable) -> Callable:
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
        func.is_reply_deferred = deferred
        return func

    if func is None:
        return decorator
    return decorator(func)


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


class Replier:
    """Replier is a helper used to handle message replies for the associated agent."""

    def __init__(self, agent: BaseAgent):
        # The associated agent.
        self._agent: BaseAgent = agent

        self._reply: Reply | None = None
        self._reply_lock: asyncio.Lock = asyncio.Lock()

    async def set_destination(self, reply: Reply) -> None:
        # Normally this operation is triggered by an orchestration agent
        # by sending a `SetReplyInfo` message to the associated agent.
        async with self._reply_lock:
            self._reply = reply

    async def get_destination(self) -> Reply | None:
        async with self._reply_lock:
            return self._reply

    async def send_to(
        self, dst: Reply, result: Message | Awaitable[Message] | AsyncIterator[Message]
    ) -> None:
        """Send the result to the given destination."""

        async def pub(msg: Message) -> None:
            if dst:
                await self._agent.channel.publish(dst.address, msg.encode())

        async def pub_exc(exc: BaseException) -> None:
            err = InternalError.from_exception(exc)
            await pub(err.encode_message())

        if dst and dst.stream:  # Streaming mode
            try:
                if is_async_iterator(result):
                    async for msg in result:
                        await pub(msg)
                elif inspect.isawaitable(result):
                    msg = await result or Empty()
                    await pub(msg)
                else:
                    await pub(result)
            except asyncio.CancelledError as exc:
                await pub_exc(exc)
                raise
            except Exception as exc:
                await pub_exc(exc)
            finally:
                # End of the iteration, send an extra StopIteration message.
                await pub(StopIteration())
        else:  # None, Deferred, or non-streaming
            try:
                if is_async_iterator(result):
                    accumulated: RawMessage | None = None
                    async for msg in result:
                        if not accumulated:
                            accumulated = msg
                        else:
                            try:
                                accumulated += msg
                            except TypeError:
                                await pub_exc(StreamError("Streaming mode is required"))
                    await pub(accumulated)
                elif inspect.isawaitable(result):
                    msg = await result or Empty()
                    await pub(msg)
                else:
                    await pub(result)
            except asyncio.CancelledError as exc:
                await pub_exc(exc)
                raise
            except Exception as exc:
                await pub_exc(exc)

    async def send(
        self,
        src: RawMessage | Message,
        result: Message | Awaitable[Message] | AsyncIterator[Message],
    ) -> bool:
        """Send the result to the preset destination; if none is set, use the destination
        provided in the source message instead.
        """
        dst = await self.get_destination() or src.reply
        await self.send_to(dst, result)
        return bool(dst)

    async def raise_exc_to(
        self,
        dst: Reply,
        exc: BaseException,
    ) -> None:
        """Convert the exception into a message and send it to the given destination."""
        err = InternalError.from_exception(exc)
        await self.send_to(dst, err.encode_message())

    async def raise_exc(
        self,
        src: RawMessage | Message,
        exc: BaseException,
    ) -> bool:
        """Convert the exception into a message and send it to the preset destination;
        if none is set, use the destination provided in the source message instead.
        """
        err = InternalError.from_exception(exc)
        return await self.send(src, err.encode_message())


class BaseAgent(Agent):
    """BaseAgent is the base class for all agents.

    Args:
        timeout (float, optional): The inactivity timeout for transitioning the
            agent state from RUNNING to IDLE. Defaults to 300 (in seconds).

            If the agent is not receiving any messages within this duration, it
            will be transitioned to the IDLE state. Once in the IDLE state, the
            agent will be deleted (recycled) by its corresponding factory agent.
    """

    def __init__(self, timeout: float = 300):
        # The following attributes will be set by the runtime after agent creation.
        self.channel: Channel | None = None
        self.address: Address | None = None
        self.factory_address: Address | None = None

        self._sub: Subscription | None = None

        # The task for handling DATA messages.
        self._handle_data_task: asyncio.Task | None = None
        self._pending_queue: asyncio.Queue[Message] = asyncio.Queue()

        self._timeout: float = timeout
        self._last_msg_received_at: float = time.time()

        # A lock to protect the access to `self._last_msg_received_at`, which
        # will be written to when receiving messages and read from when getting
        # the state of this agent.
        #
        # Note that it's possible to avoid using locks if the factory agent
        # gets the state of this agent through sending query messages, but
        # this would result in a lot of messages.
        self._last_msg_received_at_lock: asyncio.Lock = asyncio.Lock()

        self.replier = Replier(self)

        handlers, message_types = self.__collect_handlers()
        # A list of handlers that are registered to handle messages.
        self._handlers: dict[Type, Handler] = handlers
        # A list of message types associated with this agent.
        self._message_types: dict[str, Type[Message]] = {
            "Cancel": Cancel,
            "Started": Started,
            "Stopped": Stopped,
            "SetReplyInfo": SetReplyInfo,
            "ProbeAgent": ProbeAgent,
            "Empty": Empty,
            **message_types,
        }

    @property
    def id(self) -> str:
        if self.address.id:
            return f"{self.address.name}.{self.address.id}"
        else:
            return self.address.name

    def init(
        self, channel: Channel, address: Address, factory_address: Address | None = None
    ) -> None:
        self.channel = channel
        self.address = address
        self.factory_address = factory_address

    async def get_state(self) -> State:
        async with self._last_msg_received_at_lock:
            elapsed = time.time() - self._last_msg_received_at

        if elapsed >= self._timeout:
            return State.IDLE
        return State.RUNNING

    async def start(self) -> None:
        """Start the current agent."""

        # Subscribe the agent to its own address.
        self._sub = await self._create_subscription()

        # Send a `Started` message to the current agent.
        await self.channel.publish(self.address, Started().encode(), probe=False)

        if not self._handle_data_task:
            self._handle_data_task = asyncio.create_task(self._handle_data())

    async def _create_subscription(self) -> Subscription:
        # Subscribe the agent's receive method to its own address.
        return await self.channel.subscribe(self.address, handler=self.receive)

    async def stop(self) -> None:
        """Stop the current agent."""

        # Send a `Stopped` message to the current agent.
        await self.channel.publish(self.address, Stopped().encode(), probe=False)

        # Unsubscribe the agent from its own address.
        if self._sub:
            await self._sub.unsubscribe()

        if self._handle_data_task:
            self._handle_data_task.cancel()

    async def delete(self) -> None:
        """Request to delete the current agent."""
        from .factory import DeleteAgent

        if self.factory_address:
            msg = DeleteAgent(session_id=self.address.id).encode()
            await self.channel.publish(self.factory_address, msg, probe=False)

    async def started(self) -> None:
        """This handler is called after the agent is started."""
        pass

    async def stopped(self) -> None:
        """This handler is called after the agent is stopped."""
        pass

    async def receive(self, raw: RawMessage) -> None:
        name: str = f"{self.__class__.__name__} {self.id}"
        logger.debug(f"[{name}] Received a message: {raw.model_dump()}")

        async with self._last_msg_received_at_lock:
            self._last_msg_received_at = time.time()

        msg_type_name = raw.header.type
        msg_type = self._message_types.get(msg_type_name)
        if not msg_type:
            # If the message type is not found, try to use the generic message.
            msg_type = self._message_types.get("GenericMessage")
            if not msg_type:
                err = MessageDecodeError(f"message type '{msg_type_name}' not found")
                sent = await self.replier.send(raw, err.encode_message())
                if not sent:
                    logger.error(f"Failed to decode message: {err}")
                return

        try:
            msg = msg_type.decode(raw)
        except ValidationError as exc:
            err = MessageDecodeError(str(exc))
            sent = await self.replier.send(raw, err.encode_message())
            if not sent:
                logger.error(f"Failed to decode message: {err}")
            return

        if isinstance(msg, ControlMessage):
            await self._handle_control(msg)
        else:
            await self._pending_queue.put(msg)

    async def _handle_control(self, msg: ControlMessage) -> None:
        """Handle CONTROL messages."""
        match msg:
            case Cancel():
                # Delete the agent when cancelled.
                await self.delete()
            case _:
                await self._handle_control_custom(msg, Context())

    async def _handle_control_custom(self, msg: ControlMessage, ctx: Context) -> None:
        """Handle user-defined CONTROL messages."""
        h: Handler = self.__get_handler(msg)
        # By design, CONTROL messages are management commands that must be
        # processed instantly and do not wait for any return value.
        await h(self, msg, ctx)

    async def _handle_data(self) -> None:
        """Handle DATA messages."""
        while True:
            msg = await self._pending_queue.get()
            self._pending_queue.task_done()

            match msg:
                case Started():
                    await self.started()

                case Stopped():
                    await self.stopped()

                case SetReplyInfo():
                    await self.replier.set_destination(msg.reply_info)

                case ProbeAgent() | Empty():
                    # Do not handle probes and empty messages.
                    pass

                case _:
                    await self._handle_data_custom(msg, Context())

    async def _handle_data_custom(self, msg: Message, ctx: Context) -> None:
        """Handle user-defined DATA messages."""
        h: Handler = self.__get_handler(msg)
        if h.is_reply_deferred:
            # We assume that the handler returns an Awaitable[None],
            # and no need to send a reply here as it will be sent later.
            await h(self, msg, ctx)
        else:
            result = h(self, msg, ctx)
            await self.replier.send(msg, result)

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
