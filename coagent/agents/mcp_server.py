from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from typing import Any, Literal
from urllib.parse import urljoin

import aiorwlock
from coagent.core import BaseAgent, Context, handler, logger, Message
from coagent.core.messages import Cancel
from coagent.core.exceptions import InternalError
from mcp import ClientSession, Tool as MCPTool  # noqa: F401
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.types import (
    CallToolResult as MCPCallToolResult,
    ListToolsResult as MCPListToolsResult,
    ImageContent as MCPImageContent,  # noqa: F401
    TextContent as MCPTextContent,  # noqa: F401
)
from pydantic import BaseModel


# An alias of `mcp.client.stdio.StdioServerParameters`.
MCPServerStdioParams = StdioServerParameters


class MCPServerSSEParams(BaseModel):
    """Core parameters in `mcp.client.sse.sse_client`."""

    url: str
    """The URL of the server."""

    headers: dict[str, str] | None = None
    """The headers to send to the server."""

    def normalize(self) -> MCPServerSSEParams:
        if not self.url.endswith("/sse"):
            self.url = urljoin(self.url, "sse")
        return self


class Connect(Message):
    """A message to connect to the server.

    To close the server, send a `Close` message to close the connection
    and delete corresponding server agent.
    """

    transport: Literal["sse", "stdio"]
    """The transport to use.

    See https://spec.modelcontextprotocol.io/specification/2024-11-05/basic/transports/.
    """

    params: MCPServerStdioParams | MCPServerSSEParams
    """The parameters to connect to the server."""

    enable_cache: bool = True
    """Whether to cache the list result. Defaults to `True`.
    
    If `True`, the tools list will be cached and only fetched from the server
    once. If `False`, the tools list will be fetched from the server on each
    `ListTools` message. The cache can be invalidated by sending an
    `InvalidateCache` message.
    
    Only set this to `False` if you know the server will change its tools list,
    because it can drastically increase latency (by introducing a round-trip
    to the server every time).
    """


# A message to close the server.
#
# Note that this is an alias of the `Cancel` message since it's ok to close
# the server by deleting the corresponding agent.
Close = Cancel


class InvalidateCache(Message):
    """A message to invalidate the cache of the list result."""

    pass


class ListTools(Message):
    """A message to list the tools available on the server."""

    connect: Connect | None = None
    """The optional data to connect to the server (if not already connected)."""


class ListToolsResult(Message, MCPListToolsResult):
    """The result of `ListTools`."""

    pass


class CallTool(Message):
    """A message to call a tool on the server."""

    name: str
    """The name of the tool to call."""

    arguments: dict[str, Any] | None = None
    """The arguments to pass to the tool."""

    connect: Connect | None = None
    """The optional data to connect to the server (if not already connected)."""


class CallToolResult(Message, MCPCallToolResult):
    """The result of `ListTools`."""

    pass


class NamedMCPServer(BaseModel):
    name: str
    """The unique ID of the MCP server."""

    connect: Connect | None = None
    """The optional data to connect to the server (if not already connected)."""


class MCPServer(BaseAgent):
    """An agent that acts as an MCP client to connect to an MCP server."""

    def __init__(self, timeout: int = float("inf")) -> None:
        super().__init__(timeout=timeout)

        self._client_session: ClientSession | None = None
        self._exit_stack: AsyncExitStack = AsyncExitStack()

        # The lock for protecting the following three cache-related variables.
        self._cache_lock: aiorwlock.RWLock = aiorwlock.RWLock()
        self._list_tools_result_cache: ListToolsResult | None = None
        self._cache_enabled: bool = False
        self._cache_invalidated: bool = False

        # Ongoing tasks that need to be cancelled when the server is stopped.
        self._pending_tasks: set[asyncio.Task] = set()

    async def stopped(self) -> None:
        await self._close_client_session()

        if self._pending_tasks:
            # Cancel all pending tasks.
            for task in self._pending_tasks:
                task.cancel()
            self._pending_tasks.clear()

    @handler
    async def connect(self, msg: Connect, ctx: Context) -> None:
        """Connect to the server."""
        if self._client_session:
            return

        if msg.transport == "sse":
            ctx_manager: AbstractAsyncContextManager = sse_client(
                **msg.params.normalize().model_dump()
            )
        else:  # "stdio":
            ctx_manager: AbstractAsyncContextManager = stdio_client(msg.params)

        try:
            transport = await self._exit_stack.enter_async_context(ctx_manager)
            read, write = transport
            session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()

            self._client_session = session
            async with self._cache_lock.writer_lock:
                self._cache_enabled = msg.enable_cache
        except Exception as exc:
            logger.error(f"Error initializing MCP server: {exc}")
            await self._close_client_session()
            raise

    @handler
    async def invalidate_cache(self, msg: InvalidateCache, ctx: Context) -> None:
        async with self._cache_lock.writer_lock:
            self._cache_invalidated = True

    @handler(deferred=True)
    async def list_tools(self, msg: ListTools, ctx: Context) -> None:
        if not self._client_session:
            try:
                if msg.connect:
                    # Connect to the MCP server if not already connected.
                    # Note that this operation must be performed in a sequential manner.
                    await self.connect(msg.connect, ctx)
                else:
                    raise InternalError(
                        "Server not initialized. Make sure to send the `Connect` message first."
                    )
            except Exception as exc:
                await self.replier.raise_exc(msg, exc)

        async def run(msg: ListTools, ctx: Context) -> None:
            try:
                list_tools_result = self._list_tools(msg, ctx)
                await self.replier.send(msg, list_tools_result)
            except Exception as exc:
                await self.replier.raise_exc(msg, exc)

        # Handle `ListTools` messages concurrently.
        task = asyncio.create_task(run(msg, ctx))
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _list_tools(self, msg: ListTools, ctx: Context) -> ListToolsResult:
        # Return the cached result if the cache is enabled and not invalidated.
        async with self._cache_lock.reader_lock:
            if (
                self._cache_enabled
                and not self._cache_invalidated
                and self._list_tools_result_cache
            ):
                return self._list_tools_result_cache

        async with self._cache_lock.writer_lock:
            # Reset the cache status.
            self._cache_invalidated = False

            result = await self._client_session.list_tools()
            self._list_tools_result_cache = ListToolsResult(**result.model_dump())
            return self._list_tools_result_cache

    @handler(deferred=True)
    async def call_tool(self, msg: CallTool, ctx: Context) -> None:
        if not self._client_session:
            try:
                if msg.connect:
                    # Connect to the MCP server if not already connected.
                    # Note that this operation must be performed in a sequential manner.
                    await self.connect(msg.connect, ctx)
                else:
                    raise InternalError(
                        "Server not initialized. Make sure to send the `Connect` message first."
                    )
            except Exception as exc:
                await self.replier.raise_exc(msg, exc)

        async def run(msg: ListTools, ctx: Context) -> None:
            try:
                call_tool_result = await self._call_tool(msg, ctx)
                await self.replier.send(msg, call_tool_result)
            except Exception as exc:
                await self.replier.raise_exc(msg, exc)

        # Handle `CallTool` messages concurrently.
        task = asyncio.create_task(run(msg, ctx))
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _call_tool(self, msg: CallTool, ctx: Context) -> CallToolResult:
        result = await self._client_session.call_tool(msg.name, arguments=msg.arguments)
        return CallToolResult(**result.model_dump())

    async def _close_client_session(self) -> None:
        """Cleanup the client session to server."""
        try:
            await self._exit_stack.aclose()
            if self._client_session:
                self._client_session = None
        except Exception as exc:
            logger.error(f"Error closing client session: {exc}")
