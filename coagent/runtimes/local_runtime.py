from __future__ import annotations

import asyncio
import uuid
from typing import Any, AsyncIterator, Awaitable, Callable

import blinker
import pydantic

from coagent.core import (
    Address,
    BaseRuntime,
    BaseChannel,
    QueueSubscriptionIterator,
    RawMessage,
    Reply,
    StopIteration,
    Subscription,
)
from coagent.core.exceptions import (
    AgentTypeNotFoundError,
    BaseError,
    SessionIDEmptyError,
)
from coagent.core.factory import CreateAgent
from coagent.core.messages import Empty, Error
from coagent.core.types import coagent_reply_topic_prefix


class LocalRuntime(BaseRuntime):
    """An in-process runtime."""

    def __init__(self, channel: LocalChannel | None = None):
        channel = channel or LocalChannel()
        super().__init__(channel)


class LocalChannel(BaseChannel):
    """An in-process channel."""

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def subscribe(
        self,
        addr: Address,
        handler: Callable[[RawMessage], Awaitable[None]],
        queue: str = "",
    ) -> Subscription:
        return await self._subscribe(addr, handler, queue)

    async def new_reply_topic(self) -> str:
        return f"{coagent_reply_topic_prefix}{uuid.uuid4().hex}"

    async def _subscribe(
        self,
        addr: Address,
        handler: Callable[[RawMessage], Awaitable[None]] | None = None,
        queue: str = "",
    ) -> LocalChannelSubscription:
        sub = LocalChannelSubscription(addr, handler)
        await sub.subscribe()
        return sub

    async def _publish(
        self,
        addr: Address,
        msg: RawMessage,
        stream: bool = False,
        request: bool = False,
        reply: str = "",
        timeout: float = 0.5,
        probe: bool = True,
    ) -> RawMessage | None:
        if addr.is_reply or not probe or self._probe(addr):
            return await self._blinker_send(
                addr, msg, request=request, stream=stream, reply=reply, timeout=timeout
            )

        return await self._create_and_publish(
            addr, msg, request=request, stream=stream, reply=reply, timeout=timeout
        )

    async def _create_and_publish(
        self,
        addr: Address,
        msg: RawMessage,
        request: bool = False,
        stream: bool = False,
        reply: str = "",
        timeout: float = 0.5,
    ) -> RawMessage | None:
        if not addr.id:
            raise SessionIDEmptyError(f"Empty ID in addr {addr}")

        # Notify the corresponding factory to create the agent and wait for its reply.
        factory_addr = Address(name=addr.name)
        create_msg = CreateAgent(session_id=addr.id).encode()
        if not self._probe(factory_addr):
            raise AgentTypeNotFoundError(f"No factory found for agent '{addr.name}'")

        await self._blinker_send(factory_addr, create_msg, request=True)

        # Then send the original message to the agent.
        return await self._blinker_send(
            addr, msg, request=request, stream=stream, reply=reply, timeout=timeout
        )

    def _probe(self, addr: Address) -> bool:
        """Probe the existence of the agent at the given address by detecting
        whether there are any receivers for the given topic.

        See https://blinker.readthedocs.io/en/stable/#blinker.Signal.receivers.
        """
        sig = blinker.signal(addr.topic)
        return bool(sig.receivers)

    async def _blinker_send(
        self,
        addr: Address,
        msg: RawMessage,
        request: bool = False,
        stream: bool = False,
        reply: str = "",
        timeout: float = 0.5,
    ) -> RawMessage | None:
        sig = blinker.signal(addr.topic)
        # print(f"[LocalChannel] Sending message {msg} to {addr.topic}, signal: {sig}")

        # TODO: Respect the timeout.

        # **IMPORTANT**:
        # Here we assume that the first argument name of all receivers is "raw".
        # Currently, this aligns with the signature of the `BaseAgent.receive()` method.

        if not request:
            # Not in request-reply mode, just publish the message.
            await sig.send_async(None, raw=msg)
            return None
        elif reply:
            # In request-reply mode and a reply topic is given.
            # Publish the message and the response(s) will be sent to the reply topic.
            msg.reply = Reply(address=Address(name=reply), stream=stream)
            await sig.send_async(None, raw=msg)
            return None
        else:
            # In request-reply mode and no reply topic is given.
            # Wait for a response on a temporary topic and return it.
            tmp_reply = await self.new_reply_topic()
            addr = Address(name=tmp_reply)
            sub = await self._subscribe(addr)

            msg.reply = Reply(address=addr, stream=stream)
            await sig.send_async(None, raw=msg)

            result: RawMessage | None = None
            async for raw in sub.queue:
                result = raw
                break  # Just wait for the first message.

            try:
                Empty.decode(result)
                return None
            except pydantic.ValidationError:
                # Can not be converted to Empty.
                try:
                    err = Error.decode(result)
                    raise BaseError.decode_message(err)
                except pydantic.ValidationError:
                    # Can not be converted to Error, so return the message as is.
                    return result
            finally:
                await sub.unsubscribe()


class LocalChannelSubscription(Subscription):
    def __init__(
        self,
        addr: Address,
        handler: Callable[[RawMessage], Awaitable[None]] | None = None,
    ):
        self._addr = addr
        self._handler = handler

        self._queue: QueueSubscriptionIterator = QueueSubscriptionIterator()
        self._task: asyncio.Task | None = None
        self._exit_event: asyncio.Event = asyncio.Event()

    async def subscribe(self):
        sig = blinker.signal(self._addr.topic)
        sig.connect(self._receive, weak=False)

        if self._handler:
            self._task = asyncio.create_task(self._poll())

        # print(f"[LocalChannel] Connecting to {self._addr.topic}, signal: {sig}")

    async def unsubscribe(self, limit: int = 0) -> None:
        sig = blinker.signal(self._addr.topic)
        sig.disconnect(self._receive)

        if self._task:
            self._task.cancel()
            try:
                # This will raise asyncio.CancelledError if the current task was cancelled.
                await self._exit_event.wait()
            except asyncio.CancelledError:
                pass

    @property
    def queue(self) -> AsyncIterator[RawMessage]:
        return self._queue

    async def _receive(self, sender: Any, raw: RawMessage) -> None:
        await self._queue.receive(raw)

    async def _poll(self):
        try:
            async for raw in self._queue:
                await self._handler(raw)

            # End of the stream, send an extra StopIteration message.
            await self._handler(StopIteration().encode())
        except BaseError as exc:
            # Send the error as a message.
            await self._handler(exc.encode_message().encode())
        finally:
            self._exit_event.set()
