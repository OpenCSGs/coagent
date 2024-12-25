import asyncio
from typing import AsyncIterator

from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from sse_starlette.sse import EventSourceResponse

from coagent.core import Address, Channel, RawMessage, logger
from coagent.core.exceptions import BaseError
from coagent.core.factory import DeleteAgent
from coagent.core.types import Runtime
from coagent.core.util import clear_queue

from coagent.cos.agent import RemoteAgent, AgentCreated


class CosRuntime:
    def __init__(self, runtime: Runtime):
        self._runtime: Runtime = runtime
        self._agents: dict[Address, RemoteAgent] = {}

    async def start(self):
        await self._runtime.start()

    async def stop(self):
        await self._runtime.stop()

    async def register(self, request: Request):
        data: dict = await request.json()
        name: str = data["name"]
        description: str = data["description"]

        queue: asyncio.Queue[RawMessage] = asyncio.Queue()

        async def create_agent(channel: Channel, addr: Address):
            logger.debug(f"[HTTPRuntime] creating agent with addr {addr}")

            msg = AgentCreated(addr=addr)
            await queue.put(msg.encode())

            agent = RemoteAgent()
            agent.init(channel, addr)

            self._agents[addr] = agent

            return agent

        # This is a hack to convert create_agent to an instance of Constructor.
        create_agent.type = RemoteAgent

        await self._runtime.register(name, create_agent, description)

        async def event_stream() -> AsyncIterator[str]:
            try:
                while True:
                    msg = await queue.get()
                    queue.task_done()
                    yield dict(data=msg.encode_json())
            except asyncio.CancelledError:
                # Disconnected from the client.

                # Clear the queue.
                await clear_queue(queue)

                # Deregister the corresponding factory.
                await self._runtime.deregister(name)

                raise

        return EventSourceResponse(event_stream())

    async def subscribe(self, request: Request):
        data: dict = await request.json()
        addr: Address = Address.model_validate(data["addr"])

        agent: RemoteAgent = self._agents[addr]
        queue: asyncio.Queue[RawMessage] = agent.queue

        async def event_stream() -> AsyncIterator[str]:
            try:
                while True:
                    msg = await queue.get()
                    queue.task_done()
                    yield dict(data=msg.encode_json())
            except asyncio.CancelledError:
                # Disconnected from the client.

                # Delete the corresponding agent.
                factory_addr = Address(name=addr.name)
                delete_msg = DeleteAgent(session_id=addr.id).encode()
                await self._runtime.channel.publish(
                    factory_addr, delete_msg, probe=False
                )

                raise

        return EventSourceResponse(event_stream())

    async def publish(self, request: Request):
        data: dict = await request.json()
        try:
            resp: RawMessage | None = await self._runtime.channel.publish(
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

    async def publish_multi(self, request: Request):
        data: dict = await request.json()
        msgs = self._runtime.channel.publish_multi(
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
