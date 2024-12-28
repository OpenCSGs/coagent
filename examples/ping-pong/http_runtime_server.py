import os  # noqa: F401
from typing import AsyncIterator

from starlette.applications import Starlette
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


async def publish(request):
    data: dict = await request.json()
    try:
        resp: RawMessage | None = await backend.publish(
            addr=Address.model_validate(data["addr"]),
            msg=RawMessage.model_validate(data["msg"]),
            request=data.get("request", False),
            reply=data.get("reply", ""),
            timeout=data.get("timeout", 0.5),
            probe=data.get("probe", True),
        )
    except BaseError as exc:
        return JSONResponse(exc.encode(mode="json"), status_code=404)

    if resp is None:
        return Response(status_code=204)
    else:
        return JSONResponse(resp.encode(mode="json"))


async def publish_multi(request):
    data: dict = await request.json()
    msgs = backend.publish_multi(
        addr=Address.model_validate(data["addr"]),
        msg=RawMessage.model_validate(data["msg"]),
        probe=data.get("probe", True),
    )

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for raw in msgs:
                yield dict(data=raw.encode_json())
        except BaseError as exc:
            yield dict(event="error", data=exc.encode_json())

    return EventSourceResponse(event_stream())


async def subscribe(request):
    data: dict = await request.json()
    msgs: AsyncIterator[RawMessage] = backend.subscribe(
        addr=Address.model_validate(data["addr"]),
        queue=data["queue"],
    )

    async def event_stream() -> AsyncIterator[str]:
        async for raw in msgs:
            yield dict(data=raw.encode_json())

    return EventSourceResponse(event_stream())


async def new_reply_topic(request):
    topic = await backend.new_reply_topic()
    return JSONResponse(dict(reply_topic=topic))


routes = [
    Route("/publish", publish, methods=["POST"]),
    Route("/publish_multi", publish_multi, methods=["POST"]),
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
