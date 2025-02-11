import asyncio
from typing import AsyncIterator, Type

from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from sse_starlette.sse import EventSourceResponse

from coagent.core import (
    Address,
    AgentSpec,
    Constructor,
    DiscoveryQuery,
    DiscoveryReply,
    RawMessage,
    logger,
)
from coagent.core.exceptions import BaseError
from coagent.core.types import Runtime
from coagent.core.util import clear_queue

from coagent.cos.agent import RemoteAgent, AgentCreated


class _CosConstructor(Constructor):
    """A constructor for creating CoS agents."""

    def __init__(
        self, typ: Type, queue: asyncio.Queue, registry: dict[Address, RemoteAgent]
    ) -> None:
        super().__init__(typ)
        self.queue = queue
        self.registry = registry

    async def __post_call__(self, agent: RemoteAgent) -> None:
        logger.info(f"[CoS] Created agent {agent.id}")

        msg = AgentCreated(addr=agent.address)
        await self.queue.put(msg.encode())

        self.registry[agent.address] = agent


class CosRuntime:
    def __init__(self, runtime: Runtime):
        self._runtime: Runtime = runtime
        self._agents: dict[Address, RemoteAgent] = {}

    async def start(self):
        await self._runtime.start()

    async def stop(self):
        await self._runtime.stop()

    async def discover(self, request: Request):
        namespace: str = request.query_params.get("namespace", "")
        recursive: bool = request.query_params.get("recursive", "") == "true"
        inclusive: bool = request.query_params.get("inclusive", "") == "true"
        detailed: bool = request.query_params.get("detailed", "") == "true"

        result: RawMessage = await self._runtime.channel.publish(
            Address(name="discovery"),
            DiscoveryQuery(
                namespace=namespace,
                recursive=recursive,
                inclusive=inclusive,
                detailed=detailed,
            ).encode(),
            request=True,
            probe=False,
        )
        reply: DiscoveryReply = DiscoveryReply.decode(result)

        return JSONResponse(reply.model_dump(mode="json"))

    async def register(self, request: Request):
        data: dict = await request.json()
        name: str = data["name"]
        description: str = data["description"]

        queue: asyncio.Queue[RawMessage] = asyncio.Queue()

        spec = AgentSpec(
            name, _CosConstructor(RemoteAgent, queue, self._agents), description
        )
        await self._runtime.register(spec)

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
                await agent.delete()

                raise

        return EventSourceResponse(event_stream())

    async def publish(self, request: Request):
        data: dict = await request.json()

        addr: Address = Address.decode(data["addr"])
        msg: RawMessage = RawMessage.decode(data["msg"])
        stream: bool = data.get("stream", False)
        probe: bool = data.get("probe", True)

        await self._update_message_header_extensions(msg, request)

        if stream:
            return await self._publish_stream(addr, msg, probe=probe)
        else:
            return await self._publish(
                addr,
                msg,
                request=data.get("request", False),
                reply=data.get("reply", ""),
                timeout=data.get("timeout", 0.5),
                probe=probe,
            )

    async def _publish(
        self,
        addr: Address,
        msg: RawMessage,
        request: bool,
        reply: str,
        timeout: float,
        probe: bool,
    ):
        try:
            resp: RawMessage | None = await self._runtime.channel.publish(
                addr=addr,
                msg=msg,
                stream=False,
                request=request,
                reply=reply,
                timeout=timeout,
                probe=probe,
            )
        except BaseError as exc:
            return JSONResponse(exc.encode(mode="json"), status_code=404)
        except asyncio.CancelledError:
            # Disconnected from the client.

            # Cancel the ongoing operation.
            await self._runtime.channel.cancel(addr)

        if resp is None:
            return Response(status_code=204)
        else:
            return JSONResponse(resp.encode(mode="json"))

    async def _publish_stream(self, addr: Address, msg: RawMessage, probe: bool):
        msgs: AsyncIterator[RawMessage] = await self._runtime.channel.publish(
            addr=addr,
            msg=msg,
            stream=True,
            probe=probe,
        )

        async def event_stream() -> AsyncIterator[str]:
            try:
                async for raw in msgs:
                    yield dict(data=raw.encode_json())
            except BaseError as exc:
                yield dict(event="error", data=exc.encode_json())
            except asyncio.CancelledError:
                # Disconnected from the client.

                # Cancel the ongoing operation.
                await self._runtime.channel.cancel(addr)

        return EventSourceResponse(event_stream())

    async def _update_message_header_extensions(
        self, msg: RawMessage, request: Request
    ) -> None:
        """Update the message header extensions according to the request data."""
        pass
