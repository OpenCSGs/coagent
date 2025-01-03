import asyncio
from typing import AsyncIterator

import pydantic

from .discovery import Discovery
from .exceptions import BaseError
from .messages import StopIteration, Error
from .factory import Factory, DeleteAgent
from .types import (
    AgentSpec,
    Channel,
    Runtime,
    Address,
    RawMessage,
)


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

    async def register_spec(self, spec: AgentSpec) -> None:
        spec.register(self)

        if self._discovery:
            await self._discovery.register(
                spec.name, spec.constructor, spec.description
            )

        if spec.name in self._factories:
            raise ValueError(f"Agent type {spec.name} already registered")

        factory = Factory(spec.name, spec.constructor)
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

    async def delete(self, addr: Address) -> None:
        factory_addr = Address(name=addr.name)
        msg = DeleteAgent(session_id=addr.id).encode()
        await self._channel.publish(factory_addr, msg, probe=False)


class BaseChannel(Channel):
    async def publish_multi(
        self,
        addr: Address,
        msg: RawMessage,
        probe: bool = True,
    ) -> AsyncIterator[RawMessage]:
        """A default implementation that leverages the channel's own subscribe and publish methods."""
        queue: QueueSubscriptionIterator = QueueSubscriptionIterator()

        inbox = await self.new_reply_topic()
        sub = await self.subscribe(addr=Address(name=inbox), handler=queue.receive)

        await self.publish(
            addr,
            msg,
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
