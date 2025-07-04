# CoS Example


## Prerequisites

- Install `coagent` (see [Installation](../../README.md#installation)).
- Start a NATS server (see [Distributed](../../README.md#distributed)).


## Quick Start

Start the A2A server in one terminal:

```bash
python examples/a2a/app.py
```

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

Start the A2A test client:

```bash
python examples/a2a/client.py --url=http://localhost:8000/agents/translator
```
