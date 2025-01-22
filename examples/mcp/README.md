# Model Context Protocol

This example demonstrates how to implement an agent that can use tools provided by MCP ([Model Context Protocol][1]) servers.


## Prerequisites

- Install `coagent` (see [Installation](../../README.md#installation)).
- Start a NATS server (see [Distributed](../../README.md#distributed)).


## Quick Start

First start the MCP server in one terminal:

```bash
python examples/mcp/server.py
```

Then start the MCP agent in another terminal:

```bash
export AZURE_MODEL="your-model-name"
export AZURE_API_BASE="your-api-base"
export AZURE_API_VERSION="your-api-version"
export AZURE_API_KEY="your-api-key"

python examples/mcp/agent.py
```

Finally, communicate with the agent using the `coagent` CLI:

```bash
coagent mcp -H type:ChatMessage -F .content.content -d '{"role":"user","content":"What is the weather like in Beijing"}'
```


[1]: https://modelcontextprotocol.io/
