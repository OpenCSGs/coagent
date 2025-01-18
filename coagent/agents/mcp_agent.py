from typing import Any, AsyncContextManager, Callable
from urllib.parse import urljoin

from mcp import ClientSession, Tool
from mcp.types import ImageContent, TextContent
from mcp.client.sse import sse_client
import jsonschema

from .aswarm import Agent as SwarmAgent
from .chat_agent import ChatAgent, wrap_error
from .model_client import default_model_client, ModelClient


class MCPAgent(ChatAgent):
    """An agent that can use tools provided by MCP (Model Context Protocol) servers."""

    def __init__(
        self,
        system: str = "",
        mcp_server_base_url: str = "",
        client: ModelClient = default_model_client,
    ) -> None:
        super().__init__(system=system, client=client)

        self._mcp_server_base_url: str = mcp_server_base_url
        self._mcp_sse_client: AsyncContextManager[tuple] | None = None
        self._mcp_client_session: ClientSession | None = None

        self._mcp_swarm_agent: SwarmAgent | None = None

    @property
    def mcp_server_base_url(self) -> str:
        if not self._mcp_server_base_url:
            raise ValueError("MCP server base URL is empty")
        return self._mcp_server_base_url

    def make_tool(self, t: Tool) -> Callable:
        async def tool(**kwargs) -> Any:
            # Validate the input against the schema
            jsonschema.validate(instance=kwargs, schema=t.inputSchema)
            # Actually call the tool.
            result = await self._mcp_client_session.call_tool(t.name, arguments=kwargs)
            if not result.content:
                return ""
            content = result.content[0]

            if result.isError:
                raise ValueError(content.text)

            match content:
                case TextContent():
                    return content.text
                case ImageContent():
                    return content.data
                case _:  # EmbeddedResource() or other types
                    return ""

        tool.__name__ = t.name
        tool.__doc__ = t.description

        # Attach the schema and arguments to the tool.
        tool.__mcp_tool_schema__ = dict(
            name=t.name,
            description=t.description,
            parameters=t.inputSchema,
        )
        tool.__mcp_tool_args__ = t.inputSchema["properties"].keys()
        return tool

    async def get_tools(self) -> list[Callable]:
        result = await self._mcp_client_session.list_tools()
        tools = [self.make_tool(t) for t in result.tools]
        return tools

    async def get_swarm_agent(self) -> SwarmAgent:
        if not self._mcp_swarm_agent:
            tools = await self.get_tools()
            self._mcp_swarm_agent = SwarmAgent(
                name=self.name,
                model=self.client.model,
                instructions=self.system,
                functions=[wrap_error(t) for t in tools],
            )
        return self._mcp_swarm_agent

    async def started(self) -> None:
        """
        Combining `started` and `stopped` to achieve the following behavior:

            async with sse_client(url=url) as (read, write):
                async with ClientSession(read, write) as session:
                    pass
        """
        url = urljoin(self.mcp_server_base_url, "sse")
        self._mcp_sse_client = sse_client(url=url)
        read, write = await self._mcp_sse_client.__aenter__()

        self._mcp_client_session = ClientSession(read, write)
        await self._mcp_client_session.__aenter__()

        # Initialize the connection
        await self._mcp_client_session.initialize()

    async def stopped(self) -> None:
        await self._mcp_client_session.__aexit__(None, None, None)
        await self._mcp_sse_client.__aexit__(None, None, None)

    async def _handle_data(self) -> None:
        """Override the method to handle exceptions properly."""
        try:
            await super()._handle_data()
        finally:
            # Ensure the resources created in `started` are properly cleaned up.
            await self.stopped()
