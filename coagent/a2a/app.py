from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Sequence
import uuid

try:
    from a2a.types import (
        AgentCard,
        AgentCapabilities,
        JSONRPCRequest,
        SendMessageRequest,
        SendMessageResponse,
        SendMessageSuccessResponse,
        SendStreamingMessageRequest,
        SendStreamingMessageResponse,
        Message,
        Part,
        TextPart,
    )

    from sse_starlette.sse import EventSourceResponse

    from starlette.responses import Response, JSONResponse
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.requests import Request
    from starlette.routing import Route
    from starlette.types import ExceptionHandler, Lifespan
except ImportError as exc:
    raise ImportError(
        "A2A package requires a2a-sdk and starlette. "
        "Install with 'pip install coagent-python[a2a]'"
    ) from exc

from coagent.agents.messages import ChatMessage
from coagent.core import (
    Address,
    DiscoveryQuery,
    DiscoveryReply,
    RawMessage,
)
from coagent.core.discovery import Schema
from coagent.core.exceptions import BaseError
from coagent.core.types import Runtime
import httpx

from .registry import A2ARegistry


@asynccontextmanager
async def _default_lifespan(app: FastA2A) -> AsyncIterator[None]:
    await app.runtime.start()
    yield
    await app.runtime.stop()


class FastA2A(Starlette):
    def __init__(
        self,
        *,
        runtime: Runtime,
        base_url: str,
        httpx_client: httpx.AsyncClient | None = None,
        # Starlette
        debug: bool = False,
        routes: Sequence[Route] | None = None,
        middleware: Sequence[Middleware] | None = None,
        exception_handlers: dict[Any, ExceptionHandler] | None = None,
        lifespan: Lifespan[FastA2A] | None = _default_lifespan,
    ):
        super().__init__(
            debug=debug,
            routes=routes,
            middleware=middleware,
            exception_handlers=exception_handlers,
            lifespan=lifespan,
        )

        self.runtime: Runtime = runtime
        self.base_url: str = base_url

        # Setup routes for exposing Coagent agents as A2A agents.
        self.router.add_route("/agents", self.get_agent_card_list, methods=["GET"])
        self.router.add_route("/agents/{name}", self.run_agent, methods=["POST"])
        self.router.add_route(
            "/agents/{name}/.well-known/agent.json",
            self.get_agent_card,
            methods=["GET"],
        )

        if httpx_client:
            self.registry = A2ARegistry(runtime, httpx_client)

            # Setup routes for registering/deregistering A2A agents and adapting
            # them into Coagent agents.
            self.router.add_route("/agents", self.register_agent, methods=["POST"])
            self.router.add_route(
                "/agents/{name}", self.deregister_agent, methods=["DELETE"]
            )

    async def get_agent_card_list(self, request: Request) -> Response:
        cards = await self._discover_agents(
            namespace=request.query_params.get("namespace", ""),
            recursive=request.query_params.get("recursive", "") == "true",
            inclusive=request.query_params.get("inclusive", "") == "true",
            detailed=request.query_params.get("detailed", "") == "true",
        )
        return JSONResponse(
            [card.model_dump(mode="json", exclude_none=True) for card in cards]
        )

    async def get_agent_card(self, request: Request) -> Response:
        cards = await self._discover_agents(
            namespace=request.path_params["name"],
            recursive=False,
            inclusive=True,
            detailed=False,
        )
        card_dict = cards[0].model_dump(mode="json", exclude_none=True) if cards else {}
        return JSONResponse(card_dict)

    async def _discover_agents(
        self, namespace: str, recursive: bool, inclusive: bool, detailed: bool
    ) -> list[AgentCard]:
        result: RawMessage = await self.runtime.channel.publish(
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

        cards = [self._schema_to_a2a_agent_card(schema) for schema in reply.agents]
        return cards

    def _schema_to_a2a_agent_card(self, schema: Schema) -> AgentCard:
        """Convert Coagent's agent schemas to A2A's Agent Card."""
        return AgentCard(
            url=f"{self.base_url}/agents/{schema.name}",
            name=schema.name,
            description=schema.description,
            defaultInputModes=["application/json"],
            defaultOutputModes=["application/json"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[],  # TODO: from schema.operations
            version="1.0.0",
        )

    async def run_agent(self, request: Request) -> Response:
        """This is the main endpoint for the A2A server."""
        data = await request.body()
        generic_request = JSONRPCRequest.model_validate_json(data)

        name = request.path_params["name"]

        match generic_request.method:
            case "message/send":
                jsonrpc_request = SendMessageRequest.model_validate_json(data)
                jsonrpc_response = await self._send_message(name, jsonrpc_request)
                return JSONResponse(jsonrpc_response.model_dump(by_alias=True))
            case "message/stream":
                jsonrpc_request = SendStreamingMessageRequest.model_validate_json(data)
                return await self._send_message_stream(name, jsonrpc_request)
            case _:
                raise NotImplementedError(
                    f"Method {generic_request.method} not implemented."
                )

    async def _send_message(
        self, name: str, request: SendMessageRequest
    ) -> SendMessageResponse:
        """
        Note that the current implementation only works when chatting with
        agents that capable of handling `ChatMessage`.
        """
        a2a_msg = request.params.message

        session_id = a2a_msg.taskId or a2a_msg.messageId
        addr: Address = Address(name=name, id=session_id)
        msg: RawMessage = ChatMessage(
            role=a2a_msg.role,
            content=a2a_msg.parts[0].root.text,
        ).encode()

        try:
            result: RawMessage | None = await self.runtime.channel.publish(
                addr=addr,
                msg=msg,
                request=True,
                reply="",
                timeout=5,
                probe=True,
            )
        except BaseError:
            # Could not find the corresponding agent.
            raise
        except asyncio.CancelledError:
            # Disconnected from the client.

            # Cancel the ongoing operation.
            await self.runtime.channel.cancel(addr)

            raise

        if result is None:
            reply_content = "<no reply>"
        else:
            reply_content = ChatMessage.decode(result).content

        return SendMessageSuccessResponse(
            id=request.id,
            result=Message(
                role="agent",
                parts=[Part(root=TextPart(text=reply_content))],
                messageId=uuid.uuid4().hex,
                taskId=a2a_msg.taskId,
            ),
        )

    async def _send_message_stream(
        self, name: str, request: SendStreamingMessageRequest
    ) -> Response:
        """
        Note that the current implementation only works when chatting with
        agents that capable of handling `ChatMessage`.

        See https://a2aproject.github.io/A2A/v0.2.5/topics/streaming-and-async/.
        """
        a2a_msg = request.params.message

        session_id = a2a_msg.taskId or a2a_msg.messageId
        addr: Address = Address(name=name, id=session_id)
        msg: RawMessage = ChatMessage(
            role=a2a_msg.role,
            content=a2a_msg.parts[0].root.text,
        ).encode()

        msgs: AsyncIterator[RawMessage] = await self.runtime.channel.publish(
            addr=addr,
            msg=msg,
            stream=True,
            probe=True,
        )

        async def event_stream() -> AsyncIterator[str]:
            try:
                async for raw in msgs:
                    reply_content = ChatMessage.decode(raw).content
                    resp = SendStreamingMessageResponse(
                        id=request.id,
                        result=Message(
                            role="agent",
                            parts=[Part(root=TextPart(text=reply_content))],
                            messageId=uuid.uuid4().hex,
                            taskId=a2a_msg.taskId,
                        ),
                    )
                    yield dict(data=resp.model_dump_json())
            except BaseError as exc:
                yield dict(event="error", data=exc.encode_json())
            except asyncio.CancelledError:
                # Disconnected from the client.

                # Cancel the ongoing operation.
                await self.runtime.channel.cancel(addr)

        return EventSourceResponse(event_stream())

    async def register_agent(self, request: Request) -> Response:
        data = await request.json()
        url = data.get("url")
        if not url:
            return JSONResponse({"error": "url is required"}, status_code=400)

        name = await self.registry.register(url)
        return JSONResponse({"name": name})

    async def deregister_agent(self, request: Request) -> Response:
        name = request.path_params["name"]

        await self.registry.deregister(name)
        return Response(status_code=204)
