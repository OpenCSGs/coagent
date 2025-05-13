# Model Context Protocol

This example demonstrates how to implement an agent that can use tools provided by MCP ([Model Context Protocol][1]) servers.


## Prerequisites

- Install `coagent` (see [Installation](../../README.md#installation)).
- Start a NATS server (see [Distributed](../../README.md#distributed)).


## Quick Start

Set the environment variables for your model:

```bash
export MODEL_ID="your-model-id"
export MODEL_BASE_URL="your-base-url"
export MODEL_API_KEY="your-api-key"
```

### Run the local agent

Run the agent as a script:

```bash
python examples/mcp-new/local_agent.py
```

### Run the daemon agent

First start the MCP server using SSE in one terminal:

```bash
python examples/mcp-new/server.py -t sse
```

Then run the agent as a daemon in another terminal:

```bash
python examples/mcp-new/daemon_agent.py
```

Next, connect to the MCP server in the third terminal:

```bash
coagent mcp_server:server1 -H type:Connect -d '{"transport": "sse", "params": {"url": "http://localhost:8080/sse"}}'
```

Finally, communicate with the MCP agent using the `coagent` CLI:

```bash
coagent mcp -H type:ChatMessage --chat -d '{"role": "user", "content": "What is the weather like in Beijing"}'
```


[1]: https://modelcontextprotocol.io/
