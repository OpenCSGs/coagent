from __future__ import annotations

import asyncio
import json
from typing import List, Union, Callable, Awaitable

import nats
from nats.aio.client import Msg
from nats.aio.subscription import Subscription as NATSSubscription
from nats.errors import ConnectionClosedError, NoRespondersError, TimeoutError
import pydantic

from coagent.core import (
    Address,
    BaseRuntime,
    BaseChannel,
    MessageHeader,
    RawMessage,
    Reply,
    Subscription,
)
from coagent.core.exceptions import (
    AgentTypeNotFoundError,
    BaseError,
    DeadlineExceededError,
    SessionIDEmptyError,
)
from coagent.core.messages import ProbeAgent, Empty, Error
from coagent.core.factory import CreateAgent


class NATSRuntime(BaseRuntime):
    """A NATS-based runtime."""

    def __init__(self, channel: NATSChannel):
        super().__init__(channel)

    @classmethod
    def from_servers(cls, servers: Union[str, List[str], None] = None) -> NATSRuntime:
        channel = NATSChannel(servers)
        return NATSRuntime(channel)


class NATSChannel(BaseChannel):
    """A NATS-based channel."""

    def __init__(self, servers: Union[str, List[str], None] = None):
        self._servers: Union[str, List[str]] = servers or ["nats://localhost:4222"]
        self._nc: nats.NATS | None = None

    async def connect(self) -> None:
        self._nc = await nats.connect(self._servers)

    async def close(self) -> None:
        try:
            await self._nc.drain()
        except ConnectionClosedError:
            pass

    async def subscribe(
        self,
        addr: Address,
        handler: Callable[[RawMessage], Awaitable[None]],
        queue: str = "",
    ) -> Subscription:
        async def receive(msg: Msg) -> None:
            raw = nats_msg_to_raw(msg)
            await handler(raw)

        sub = await self._nc.subscribe(addr.topic, queue=queue, cb=receive)
        return NATSChannelSubscription(sub)

    async def new_reply_topic(self) -> str:
        return self._nc.new_inbox()

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
        if addr.is_reply or not probe or await self._probe(addr):
            return await self._nats_publish(
                addr, msg, request=request, stream=stream, reply=reply, timeout=timeout
            )

        if request:
            # If in request-reply (or non-blocking) mode, always wait for the reply.
            return await self._create_and_publish(
                addr,
                msg,
                request=request,
                stream=stream,
                reply=reply,
                timeout=timeout,
            )

        # Run in a separate task to avoid blocking the agent handler.
        _ = asyncio.create_task(
            self._create_and_publish(
                addr, msg, request=request, stream=stream, reply=reply, timeout=timeout
            )
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
        try:
            # Wait at most 5 seconds for the factory to create an agent.
            await self._nats_publish(factory_addr, create_msg, request=True, timeout=5)
        except NoRespondersError:
            raise AgentTypeNotFoundError(f"No factory found for agent '{addr.name}'")
        except TimeoutError:
            raise DeadlineExceededError(
                f"Factory {factory_addr.name} is too slow to respond"
            )

        # Then send the original message to the agent.
        return await self._nats_publish(
            addr, msg, request=request, stream=stream, reply=reply, timeout=timeout
        )

    async def _probe(self, addr: Address) -> bool:
        """Probe the existence of the agent at the given address by leveraging
        the `No responders` mechanism of NATS to check if there are available
        subscribers for the given topic.

        See https://docs.nats.io/nats-concepts/core-nats/reqreply#no-responders.

        Note that this might not be the best way since it will introduce a small
        delay to each publish operation.
        """
        try:
            await self._nats_publish(
                addr, ProbeAgent().encode(), request=True, timeout=0.01
            )  # 10ms
        except NoRespondersError:
            return False
        except Exception:
            return True
        else:
            return True

    async def _nats_publish(
        self,
        addr: Address,
        msg: RawMessage,
        request: bool = False,
        stream: bool = False,
        reply: str = "",
        timeout: float = 0.5,
    ) -> RawMessage | None:
        topic = addr.topic
        headers = {
            "Coagent-Type": msg.header.type,
            "Coagent-Content-Type": msg.header.content_type,
            "Coagent-Extensions": json.dumps(msg.header.extensions),
            "Coagent-Stream": "true" if stream else "false",
        }
        payload = msg.content

        if not request:
            # Not in request-reply mode, just publish the message.
            return await self._nc.publish(topic, payload, headers=headers)
        elif reply:
            # In request-reply mode and a reply topic is given.
            # Publish the message and the response(s) will be sent to the reply topic.
            return await self._nc.publish(topic, payload, reply=reply, headers=headers)
        else:
            # In request-reply mode and no reply topic is given.
            # Publish the message and wait for a response on a temporary topic.
            result = await self._nc.request(
                topic, payload, timeout=timeout, headers=headers
            )
            result_msg = nats_msg_to_raw(result)
            try:
                Empty.decode(result_msg)
                return None
            except pydantic.ValidationError:
                # Can not be converted to Empty.
                try:
                    err = Error.decode(result_msg)
                    raise BaseError.decode_message(err)
                except pydantic.ValidationError:
                    # Can not be converted to Error, so return the message as is.
                    return result_msg


class NATSChannelSubscription(Subscription):
    def __init__(self, sub: NATSSubscription):
        self._sub: NATSSubscription = sub

    async def unsubscribe(self, limit: int = 0) -> None:
        try:
            await self._sub.unsubscribe(limit)
        except ConnectionClosedError:
            pass


def nats_msg_to_raw(msg: Msg) -> RawMessage:
    header = MessageHeader(
        type=msg.header.get("Coagent-Type"),
        content_type=msg.header.get("Coagent-Content-Type"),
        extensions=json.loads(msg.header.get("Coagent-Extensions", "{}")),
    )
    raw = RawMessage(
        header=header,
        content=msg.data,
    )
    if msg.reply:
        stream = msg.header.get("Coagent-Stream") == "true"
        raw.reply = Reply(address=Address(name=msg.reply), stream=stream)
    return raw
