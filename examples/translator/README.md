# Translator


## Prerequisites

- Install `coagent` (see [Installation](../../README.md#installation)).
- Start a NATS server (see [Distributed](../../README.md#distributed)).


## Quick Start

First, start a server in one terminal:

```bash
export MODEL_ID="your-model-id"
export MODEL_BASE_URL="your-base-url"
export MODEL_API_VERSION="your-api-version"
export MODEL_API_KEY="your-api-key"

python examples/translator/translator.py
```

Then communicate with the agent using the `coagent` CLI:

```bash
coagent translator -H type:ChatHistory -d '{"messages":[{"role":"user","content":"你好"}]}' --chat
```

Or start a more-friendly rich client in another terminal:

```bash
python examples/rich_client.py translator
```
