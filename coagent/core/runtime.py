import abc
import asyncio
from typing import AsyncIterator, Awaitable, Callable

import pydantic

from .discovery import Discovery
from .exceptions import BaseError
from .messages import Cancel, Error, StopIteration
from .factory import Factory
from .types import (
    AgentSpec,
    Channel,
    Runtime,
    Address,
    RawMessage,
    Subscription,
)
from .util import wait_for_shutdown


class BaseRuntime(Runtime):
    def __init__(self, channel: Channel):
        self._channel: Channel = channel
        self._discovery: Discovery | None = None
        self._factories: dict[str, Factory] = {}

    async def start(self) -> None:
        await self._channel.connect()

        self._discovery = Discovery()
        # We MUST set the channel and address manually.
        self._discovery.init(self._channel, Address(name="discovery"))
        await self._discovery.start()

    async def stop(self) -> None:
        await self._discovery.stop()
        await self.deregister()
        await self._channel.close()

    async def wait_for_shutdown(self, timeout: float | None = None) -> None:
        await wait_for_shutdown(timeout)

    async def register(self, spec: AgentSpec) -> None:
        spec.register(self)

        if self._discovery:
            await self._discovery.register(spec)

        if spec.name in self._factories:
            raise ValueError(f"Agent type {spec.name} already registered")

        factory = Factory(spec)
        # We MUST set the channel and address manually.
        factory.init(self._channel, Address(name=spec.name))
        self._factories[spec.name] = factory

        await factory.start()

    async def deregister(self, *names: str) -> None:
        if names:
            for name in names:
                factory = self._factories.pop(name, None)
                if factory:
                    await factory.stop()
        else:
            for factory in self._factories.values():
                await factory.stop()
            self._factories.clear()

        if self._discovery:
            await self._discovery.deregister(*names)

    @property
    def channel(self) -> Channel:
        return self._channel


class BaseChannel(Channel):
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
        if stream:
            return self._publish_stream(addr, msg, probe=probe)
        else:
            return await self._publish(
                addr,
                msg,
                request=request,
                stream=stream,
                reply=reply,
                timeout=timeout,
                probe=probe,
            )

    @abc.abstractmethod
    async def _publish(
        self,
        addr: Address,
        msg: RawMessage,
        request: bool = False,
        stream: bool = False,
        reply: str = "",
        timeout: float = 0.5,
        probe: bool = True,
    ) -> RawMessage | None:
        pass

    async def _publish_stream(
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

        This is a default implementation that leverages the channel's own subscribe and _publish methods.
        """
        queue: QueueSubscriptionIterator = QueueSubscriptionIterator()

        inbox = await self.new_reply_topic()
        sub = await self.subscribe(addr=Address(name=inbox), handler=queue.receive)

        await self._publish(
            addr,
            msg,
            stream=True,
            request=True,
            reply=inbox,
            probe=probe,
        )

        try:
            async for msg in queue:
                try:
                    err = Error.decode(msg)
                    raise BaseError.decode_message(err)
                except pydantic.ValidationError:
                    yield msg
        finally:
            await sub.unsubscribe()

    async def cancel(self, addr: Address) -> None:
        """Cancel the agent with the given address."""

        # A shortcut for sending a Cancel message to the agent.
        await self.publish(addr, Cancel().encode(), probe=False)


class QueueSubscriptionIterator:
    """A Queue-based async iterator that receives messages from a subscription and yields them."""

    def __init__(self):
        self.queue: asyncio.Queue[RawMessage] = asyncio.Queue()

    async def receive(self, raw: RawMessage) -> None:
        await self.queue.put(raw)

    async def __anext__(self) -> RawMessage:
        msg = await self.queue.get()
        self.queue.task_done()
        try:
            # If it's a StopIteration message, end the iteration.
            StopIteration.decode(msg)
            raise StopAsyncIteration
        except pydantic.ValidationError:
            try:
                err = Error.decode(msg)
                raise BaseError.decode_message(err)
            except pydantic.ValidationError:
                return msg

    def __aiter__(self):
        return self


class NopChannel(Channel):
    """A no-op channel mainly for testing purposes."""

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

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
        pass

    async def subscribe(
        self,
        addr: Address,
        handler: Callable[[RawMessage], Awaitable[None]],
        queue: str = "",
    ) -> Subscription:
        pass

    async def new_reply_topic(self) -> str:
        return ""

    async def cancel(self, addr: Address) -> None:
        pass
