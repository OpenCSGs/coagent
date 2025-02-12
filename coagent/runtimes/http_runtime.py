from __future__ import annotations

import asyncio
from typing import AsyncIterator, Awaitable, Callable

import httpx
from httpx_sse import aconnect_sse

from coagent.core import (
    Address,
    BaseRuntime,
    BaseChannel,
    Channel,
    logger,
    RawMessage,
    QueueSubscriptionIterator,
    StopIteration,
    Subscription,
)
from coagent.core.exceptions import BaseError


http2_client = httpx.AsyncClient(http2=True)


class HTTPRuntime(BaseRuntime):
    """An HTTP-based runtime."""

    def __init__(self, channel: HTTPChannel):
        super().__init__(channel)

    @classmethod
    def from_server(cls, server: str, auth: str = "") -> HTTPRuntime:
        """
        Args:
            server (str): The server address.
            auth (str, optional): The authentication credential. Defaults to "".
        """
        channel = HTTPChannel(server, auth)
        return HTTPRuntime(channel)


class HTTPChannel(BaseChannel):
    """An HTTP-based channel.

    _publish: POST /publish
    _publish_stream: POST /publish stream=True
    subscribe: POST /subscribe
    new_reply_topic: POST /reply-topics
    """

    def __init__(self, server: str, auth: str = ""):
        """
        Args:
            server (str): The server address.
            auth (str, optional): The authentication credential. Defaults to "".
        """
        self._server: str = server
        self._auth: str = auth

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def _publish(
        self,
        addr: Address,
        msg: RawMessage,
        stream: bool = False,
        request: bool = False,
        reply: str = "",
        timeout: float = 5.0,
        probe: bool = True,
    ) -> RawMessage | None:
        data = dict(
            addr=addr.encode(mode="json"),
            msg=msg.encode(mode="json"),
            stream=stream,
            request=request,
            reply=reply,
            timeout=timeout,
            probe=probe,
        )
        headers = {"Authorization": self._auth} if self._auth else None

        resp = await http2_client.post(
            f"{self._server}/publish", json=data, headers=headers, timeout=timeout
        )

        if resp.status_code == 200:
            return RawMessage.model_validate_json(resp.content)

        if resp.is_error:
            raise_http_error(resp, resp.text)

    async def _publish_stream(
        self,
        addr: Address,
        msg: RawMessage,
        probe: bool = True,
    ) -> AsyncIterator[RawMessage]:
        """
        Note that we do not use the default implementation from BaseChannel,
        because multiple HTTP calls will result in poor performance.
        """
        data = dict(
            addr=addr.encode(mode="json"),
            msg=msg.encode(mode="json"),
            stream=True,
            request=True,
            probe=probe,
        )
        headers = {"Authorization": self._auth} if self._auth else None

        queue: QueueSubscriptionIterator = QueueSubscriptionIterator()
        sub: HTTPChannelSubscription = HTTPChannelSubscription(
            f"{self._server}/publish", data, headers, queue.receive
        )
        await sub.subscribe()

        try:
            async for msg in queue:
                yield msg
        finally:
            await sub.unsubscribe()

    async def subscribe(
        self,
        addr: Address,
        handler: Callable[[RawMessage], Awaitable[None]],
        queue: str = "",
    ) -> Subscription:
        data = dict(
            addr=addr.encode(mode="json"),
            queue=queue,
        )
        headers = {"Authorization": self._auth} if self._auth else None

        sub = HTTPChannelSubscription(
            f"{self._server}/subscribe", data, headers, handler
        )
        await sub.subscribe()
        return sub

    async def new_reply_topic(self) -> str:
        data = dict()
        headers = {"Authorization": self._auth} if self._auth else None

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._server}/reply-topics", json=data, headers=headers
            )
            result = resp.json()
            return result["reply_topic"]


class HTTPChannelSubscription(Subscription):
    """A subscription created when subscribing to an HTTP-based channel."""

    def __init__(
        self,
        url: str,
        data: dict,
        headers: dict | None,
        handler: Callable[[RawMessage], Awaitable[None]],
    ):
        self._url: str = url
        self._data: dict = data
        self._headers: dict | None = headers
        self._handler: Callable[[RawMessage], Awaitable[None]] = handler

        self._task: asyncio.Task = asyncio.create_task(self._poll())
        self._subscribe_event: asyncio.Event = asyncio.Event()
        self._exit_event: asyncio.Event = asyncio.Event()

    async def subscribe(self):
        # Wait until the subscription is created.
        await self._subscribe_event.wait()

    async def unsubscribe(self, limit: int = 0) -> None:
        """Align to NATS for simplicity."""
        self._task.cancel()
        try:
            # This will raise asyncio.CancelledError if the current task was cancelled.
            await self._exit_event.wait()
        except asyncio.CancelledError:
            pass

    async def _poll(self) -> None:
        while True:
            async with httpx.AsyncClient(timeout=None) as client:
                try:
                    async with aconnect_sse(
                        client,
                        "POST",
                        self._url,
                        json=self._data,
                        headers=self._headers or {},
                    ) as event_source:
                        if not self._subscribe_event.is_set():
                            # Notify that the subscription is created.
                            self._subscribe_event.set()

                        async for sse in event_source.aiter_sse():
                            data_str = sse.data

                            # There's no standard way to send errors in SSE (https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events).
                            # Here we assume that if the event is "error", an error has occurred on the server side.
                            #
                            # For error handling on the SSE server side, see `publish_multi()`
                            # in examples/ping-pong/http_runtime_server.py
                            if sse.event == "error":
                                raise_http_error(event_source.response, data_str)

                            raw: RawMessage = RawMessage.model_validate_json(data_str)
                            await self._handler(raw)

                        # End of the stream, send an extra StopIteration message.
                        await self._handler(StopIteration().encode())
                        # Exit the loop.
                        self._exit_event.set()
                        break
                # except (BaseError, httpx.HTTPStatusError) as exc:
                except BaseError as exc:
                    # Send the error as a message.
                    await self._handler(exc.encode_message().encode())
                    break
                except asyncio.CancelledError:
                    # User cancelled, close the client and exit.
                    await client.aclose()
                    # TODO: We use break here since using raise doesn't work as expected.
                    break
                except Exception as exc:
                    # Other errors, reconnect in 3 seconds
                    logger.exception(f"Error occurred: {type(exc)}, {exc}")
                    await asyncio.sleep(3)

        self._exit_event.set()


def raise_http_error(resp: httpx.Response, error_str: str | bytes):
    try:
        exc = BaseError.decode_json(error_str)
        raise exc
    except ValueError:
        raise httpx.HTTPStatusError(error_str, request=resp.request, response=resp)


class HTTPChannelBackend:
    """A backend for the HTTP-based channel.

    This helper backend is typically used in conjunction with Starlette or
    FastAPI on the server side.

    See examples/ping-pong/http_runtime_server.py for a reference server implementation.
    """

    def __init__(self, channel: Channel):
        self._channel: Channel = channel

    async def start(self):
        await self._channel.connect()

    async def stop(self):
        await self._channel.close()

    async def publish(
        self,
        addr: Address,
        msg: RawMessage,
        stream: bool = False,
        request: bool = False,
        reply: str = "",
        timeout: float = 5.0,
        probe: bool = True,
    ) -> AsyncIterator[RawMessage] | RawMessage | None:
        return await self._channel.publish(
            addr,
            msg,
            stream=stream,
            request=request,
            reply=reply,
            timeout=timeout,
            probe=probe,
        )

    async def subscribe(
        self,
        addr: Address,
        queue: str = "",
    ) -> AsyncIterator[RawMessage]:
        msg_queue: QueueSubscriptionIterator = QueueSubscriptionIterator()

        sub = await self._channel.subscribe(
            addr, handler=msg_queue.receive, queue=queue
        )

        try:
            async for msg in msg_queue:
                yield msg
        finally:
            await sub.unsubscribe()

    async def new_reply_topic(self) -> str:
        return await self._channel.new_reply_topic()
