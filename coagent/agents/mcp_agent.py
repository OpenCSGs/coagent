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
from .model import default_model, Model


@dataclasses.dataclass
class Prompt:
    name: str
    arguments: dict[str, str] | None = None


class MCPAgent(ChatAgent):
    """An agent that can use prompts and tools provided by MCP (Model Context Protocol) servers."""

    def __init__(
        self,
        mcp_server_base_url: str = "",
        mcp_server_headers: dict[str, Any] | None = None,
        system: Prompt | str = "",
        tools: list[str] | None = None,
        model: Model = default_model,
    ) -> None:
        super().__init__(system="", model=model)

        self._mcp_server_base_url: str = mcp_server_base_url
        self._mcp_server_headers: dict[str, Any] | None = mcp_server_headers

        self._mcp_client_transport: AsyncContextManager[tuple] | None = None
        self._mcp_client_session: ClientSession | None = None

        self._mcp_swarm_agent: SwarmAgent | None = None
        self._mcp_system_prompt_config: Prompt | str = system
        # The selected tools to use. If None, all available tools will be used.
        self._mcp_selected_tools: list[str] | None = tools

    @property
    def mcp_server_base_url(self) -> str:
        if not self._mcp_server_base_url:
            raise ValueError("MCP server base URL is empty")
        return self._mcp_server_base_url

    @property
    def mcp_server_headers(self) -> dict[str, Any] | None:
        return self._mcp_server_headers

    @property
    def system(self) -> Prompt | str:
        """Note that this property is different from the `system` property in ChatAgent."""
        return self._mcp_system_prompt_config

    @property
    def tools(self) -> list[str] | None:
        """Note that this property is different from the `tools` property in ChatAgent."""
        return self._mcp_selected_tools

    def _make_mcp_client_transport(self) -> AsyncContextManager[tuple]:
        if self.mcp_server_base_url.startswith(("http://", "https://")):
            url = urljoin(self.mcp_server_base_url, "sse")
            return sse_client(url=url, headers=self.mcp_server_headers)
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
            system = await self._get_prompt(self.system)
            tools = await self._get_tools(self.tools)
            self._mcp_swarm_agent = SwarmAgent(
                name=self.name,
                model=self.model.id,
                instructions=system,
                functions=[wrap_error(t) for t in tools],
            )
        return self._mcp_swarm_agent

    async def _get_prompt(self, prompt_config: Prompt | str) -> str:
        if isinstance(prompt_config, str):
            # The system prompt is a string, just return it as is.
            return prompt_config

        try:
            prompt = await self._mcp_client_session.get_prompt(
                **dataclasses.asdict(prompt_config),
            )
        except McpError as exc:
            raise InternalError(str(exc))

        content = prompt.messages[0].content
        match content:
            case TextContent():
                return content.text
            case _:  # ImageContent() or EmbeddedResource() or other types
                return ""

    async def _get_tools(self, selected_tools: list[str] | None) -> list[Callable]:
        result = await self._mcp_client_session.list_tools()

        def filter_tool(t: Tool) -> bool:
            if selected_tools is None:
                return True
            return t.name in selected_tools

        tools = [self._make_tool(t) for t in result.tools if filter_tool(t)]

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
