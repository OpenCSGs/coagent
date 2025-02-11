import argparse
import asyncio
from hypercorn.asyncio import serve
from hypercorn.config import Config
from starlette.applications import Starlette
from starlette.routing import Route

from coagent.cos.runtime import CosRuntime
from coagent.core import set_stderr_logger
from coagent.runtimes import NATSRuntime, HTTPRuntime


class Application:
    def __init__(self, server: str, auth: str):
        if server.startswith("nats://"):
            runtime = NATSRuntime.from_servers(server)
        elif server.startswith(("http://", "https://")):
            runtime = HTTPRuntime.from_server(server, auth)
        else:
            raise ValueError(f"Unsupported server: {server}")
        self.runtime = CosRuntime(runtime)

    async def startup(self):
        await self.runtime.start()

    async def shutdown(self):
        await self.runtime.stop()

    @property
    def starlette(self) -> Starlette:
        routes = [
            Route(
                "/runtime/register",
                self.runtime.register,
                methods=["POST"],
            ),
            Route(
                "/runtime/channel/subscribe",
                self.runtime.subscribe,
                methods=["POST"],
            ),
            Route(
                "/runtime/channel/publish",
                self.runtime.publish,
                methods=["POST"],
            ),
        ]
        return Starlette(
            debug=True,
            routes=routes,
            on_startup=[self.startup],
            on_shutdown=[self.shutdown],
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--listen",
        type=str,
        default="127.0.0.1:8000",
        help="The listen address of the CoS server. (Defaults to %(default)r)",
    )
    parser.add_argument(
        "--server",
        type=str,
        default="nats://localhost:4222",
        help="The runtime server address. (Defaults to %(default)r)",
    )
    parser.add_argument(
        "--auth",
        type=str,
        default="",
        help="The runtime server authentication token. (Defaults to %(default)r)",
    )
    args = parser.parse_args()

    set_stderr_logger()
    app = Application(args.server, args.auth).starlette

    config = Config()
    config.bind = [args.listen]
    asyncio.run(serve(app, config))
