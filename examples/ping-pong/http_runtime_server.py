import os  # noqa: F401
from typing import AsyncIterator

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.routing import Route
from sse_starlette.sse import EventSourceResponse

from coagent.core import Address, RawMessage
from coagent.core.exceptions import BaseError
from coagent.runtimes import HTTPChannelBackend, LocalChannel, NATSChannel  # noqa: F401


# NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
# channel = NATSChannel(NATS_URL)
channel = LocalChannel()
backend = HTTPChannelBackend(channel)


async def startup():
    await backend.start()


async def shutdown():
    await backend.stop()


async def publish(request: Request):
    data: dict = await request.json()

    addr: Address = Address.model_validate(data["addr"])
    msg: RawMessage = RawMessage.model_validate(data["msg"])
    stream: bool = data.get("stream", False)
    _request: bool = data.get("request", False)
    reply: str = data.get("reply", "")
    timeout: float = data.get("timeout", 0.5)
    probe: bool = data.get("probe", True)

    # Streaming
    if stream:
        msgs: AsyncIterator[RawMessage] = await backend.publish(
            addr=addr, msg=msg, stream=stream, probe=probe
        )

        async def event_stream() -> AsyncIterator[str]:
            try:
                async for raw in msgs:
                    yield dict(data=raw.encode_json())
            except BaseError as exc:
                yield dict(event="error", data=exc.encode_json())

        return EventSourceResponse(event_stream())

    # Non-streaming
    try:
        resp: RawMessage | None = await backend.publish(
            addr=addr,
            msg=msg,
            stream=stream,
            request=_request,
            reply=reply,
            timeout=timeout,
            probe=probe,
        )
    except BaseError as exc:
        return JSONResponse(exc.encode(mode="json"), status_code=404)

    if resp is None:
        return Response(status_code=204)
    else:
        return JSONResponse(resp.encode(mode="json"))


async def subscribe(request: Request):
    data: dict = await request.json()
    msgs: AsyncIterator[RawMessage] = backend.subscribe(
        addr=Address.model_validate(data["addr"]),
        queue=data["queue"],
    )

    async def event_stream() -> AsyncIterator[str]:
        async for raw in msgs:
            yield dict(data=raw.encode_json())

    return EventSourceResponse(event_stream())


async def new_reply_topic(request: Request):
    topic = await backend.new_reply_topic()
    return JSONResponse(dict(reply_topic=topic))


routes = [
    Route("/publish", publish, methods=["POST"]),
    Route("/subscribe", subscribe, methods=["POST"]),
    Route("/reply-topics", new_reply_topic, methods=["POST"]),
]


app = Starlette(debug=True, routes=routes, on_startup=[startup], on_shutdown=[shutdown])


if __name__ == "__main__":
    import asyncio
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    config = Config()
    config.bind = ["127.0.0.1:8000"]
    asyncio.run(serve(app, config))
