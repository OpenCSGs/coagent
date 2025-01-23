import dataclasses
from typing import Any, AsyncContextManager, Callable
from urllib.parse import urljoin

from coagent.core.exceptions import InternalError
from mcp import ClientSession, Tool, McpError
from mcp.types import ImageContent, TextContent
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client, StdioServerParameters
import jsonschema

from .aswarm import Agent as SwarmAgent
from .chat_agent import ChatAgent, wrap_error
from .model_client import default_model_client, ModelClient


@dataclasses.dataclass
class Prompt:
    name: str
    arguments: dict[str, str] | None = None


class MCPAgent(ChatAgent):
    """An agent that can use tools provided by MCP (Model Context Protocol) servers."""

    def __init__(
        self,
        system: Prompt | None = None,
        mcp_server_base_url: str = "",
        client: ModelClient = default_model_client,
    ) -> None:
        super().__init__(system="", client=client)

        self._mcp_server_base_url: str = mcp_server_base_url
        self._mcp_client_transport: AsyncContextManager[tuple] | None = None
        self._mcp_client_session: ClientSession | None = None

        self._mcp_swarm_agent: SwarmAgent | None = None
        self._mcp_system_prompt: Prompt | None = system

    @property
    def mcp_server_base_url(self) -> str:
        if not self._mcp_server_base_url:
            raise ValueError("MCP server base URL is empty")
        return self._mcp_server_base_url

    def _make_mcp_client_transport(self) -> AsyncContextManager[tuple]:
        if self.mcp_server_base_url.startswith(("http://", "https://")):
            url = urljoin(self.mcp_server_base_url, "sse")
            return sse_client(url=url)
        else:
            # Mainly for testing purposes.
            command, arg = self.mcp_server_base_url.split(" ", 1)
            params = StdioServerParameters(command=command, args=[arg])
            return stdio_client(params)

    async def started(self) -> None:
        """
        Combining `started` and `stopped` to achieve the following behavior:

            async with sse_client(url=url) as (read, write):
                async with ClientSession(read, write) as session:
                    pass
        """
        self._mcp_client_transport = self._make_mcp_client_transport()
        read, write = await self._mcp_client_transport.__aenter__()

        self._mcp_client_session = ClientSession(read, write)
        await self._mcp_client_session.__aenter__()

        # Initialize the connection
        await self._mcp_client_session.initialize()

    async def stopped(self) -> None:
        await self._mcp_client_session.__aexit__(None, None, None)
        await self._mcp_client_transport.__aexit__(None, None, None)

    async def _handle_data(self) -> None:
        """Override the method to handle exceptions properly."""
        try:
            await super()._handle_data()
        finally:
            # Ensure the resources created in `started` are properly cleaned up.
            await self.stopped()

    async def get_swarm_agent(self) -> SwarmAgent:
        if not self._mcp_swarm_agent:
            system = await self._get_system_prompt()
            tools = await self._get_tools()
            self._mcp_swarm_agent = SwarmAgent(
                name=self.name,
                model=self.client.model,
                instructions=system,
                functions=[wrap_error(t) for t in tools],
            )
        return self._mcp_swarm_agent

    async def _get_system_prompt(self) -> str:
        if not self._mcp_system_prompt:
            return ""

        try:
            prompt = await self._mcp_client_session.get_prompt(
                **dataclasses.asdict(self._mcp_system_prompt),
            )
        except McpError as exc:
            raise InternalError(str(exc))

        content = prompt.messages[0].content
        match content:
            case TextContent():
                return content.text
            case _:  # ImageContent() or EmbeddedResource() or other types
                return ""

    async def _get_tools(self) -> list[Callable]:
        result = await self._mcp_client_session.list_tools()
        tools = [self._make_tool(t) for t in result.tools]
        return tools

    def _make_tool(self, t: Tool) -> Callable:
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
        tool.__mcp_tool_args__ = tuple(t.inputSchema["properties"].keys())
        return tool
