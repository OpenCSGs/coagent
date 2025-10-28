# Model Context Protocol

This example demonstrates how to use [MCP][1] tools in a ReAct agent.


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

Run the MCP server:

```bash
python examples/react-mcp/server.py
```

Run the agent:

```bash
python examples/react-mcp/agent.py
```

```
I'll check the weather in Beijing for you right away.
[tool#call_hs9xiswsunbcynv946n43z46 call: get_weather]

[tool#call_hs9xiswsunbcynv946n43z46 progress: Getting weather for Beijing]

[tool#call_hs9xiswsunbcynv946n43z46 output: The weather in Beijing is sunny.]
The weather in Beijing is sunny today! It looks like a beautiful day there.
```


[1]: https://modelcontextprotocol.io/
