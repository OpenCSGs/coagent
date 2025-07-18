# A2A Example


## Prerequisites

- Install `coagent` (see [Installation](../../README.md#installation)).
- Start a NATS server (see [Distributed](../../README.md#distributed)).


## Quick Start

Start the A2A server in one terminal:

```bash
python examples/a2a/app.py
```

### Convert Coagent agents to A2A agents

Then run the [translator](../translator/README.md) agent in another terminal:

```bash
export MODEL_ID="your-model-id"
export MODEL_BASE_URL="your-base-url"
export MODEL_API_VERSION="your-api-version"
export MODEL_API_KEY="your-api-key"

python examples/translator/translator.py
```

Discover all available agents:

```bash
curl http://localhost:8000/agents | jq
```

Run the A2A test client:

```bash
python examples/a2a/client.py --url=http://localhost:8000/agents/translator
```

### Convert A2A agents to Coagent agents

Run A2A agent (see [Helloworld Example](https://github.com/a2aproject/a2a-python#helloworld-example)):

```bash
git clone https://github.com/a2aproject/a2a-samples.git
cd a2a-samples/samples/python/agents/helloworld
uv run .
```

Register the A2A agent:

```bash
curl -XPOST http://localhost:8000/agents -d '{"url": "http://localhost:9999"}'
{"name":"hello_world_agent"}
```

Or deregister the A2A agent:

```bash
curl -XDELETE http://localhost:8000/agents/hello_world_agent
```

Communicate with the agent using the `coagent` CLI:

```bash
coagent hello_world_agent -H type:ChatMessage -d '{"role":"user", "content":"hello"}' --chat
```
