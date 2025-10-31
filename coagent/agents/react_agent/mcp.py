from dataclasses import dataclass

import mcputil


@dataclass
class MCPTools:
    """A loader for MCP tools. This class can be used to load a subset of tools from an MCP server."""

    client: mcputil.Client
    """The MCP client to use for loading the tools."""

    include: list[str] | None = None
    """The list of tool names to include. If None, all tools are included."""

    exclude: list[str] | None = None
    """The list of tool names to exclude. If None, no tools are excluded."""

    async def load(self) -> list[mcputil.Tool]:
        return await self.client.get_tools(include=self.include, exclude=self.exclude)

    async def connect(self) -> None:
        await self.client.connect()

    async def close(self) -> None:
        await self.client.close()
