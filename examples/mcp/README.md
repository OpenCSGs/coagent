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
export AZURE_MODEL=csg-gpt4
export AZURE_API_BASE=https://opencsg-us.openai.azure.com
export AZURE_API_VERSION=2024-02-15-preview
export AZURE_API_KEY=<YOUR API KEY>

python examples/mcp/agent.py
```

Finally, communicate with the agent using the `coagent` CLI:

```bash
coagent mcp -H type:ChatMessage -F .content.content -d '{"role":"user","content":"What is the weather like in Beijing"}'
```


[1]: https://modelcontextprotocol.io/
