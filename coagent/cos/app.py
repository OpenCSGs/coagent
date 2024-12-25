from starlette.applications import Starlette
from starlette.routing import Route

from coagent.cos.runtime import CosRuntime
from coagent.runtimes import NATSRuntime, LocalRuntime
from coagent.core.util import get_nats_servers

runtime = CosRuntime(NATSRuntime.from_servers(servers=get_nats_servers()))


async def startup():
    await runtime.start()


async def shutdown():
    await runtime.stop()


routes = [
    Route("/runtime/register", runtime.register, methods=["POST"]),
    Route("/runtime/channel/subscribe", runtime.subscribe, methods=["POST"]),
    Route("/runtime/channel/publish", runtime.publish, methods=["POST"]),
    Route("/runtime/channel/publish_multi", runtime.publish_multi, methods=["POST"]),
]


app = Starlette(debug=True, routes=routes, on_startup=[startup], on_shutdown=[shutdown])


if __name__ == "__main__":
    import asyncio
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    config = Config()
    config.bind = ["127.0.0.1:8000"]
    asyncio.run(serve(app, config))
