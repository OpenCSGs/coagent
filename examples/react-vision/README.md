# ReAct Vision

This example demonstrates how to handle images using a vision model (e.g. gemini-2.5-flash) in a ReAct agent.


## Prerequisites

- Install `coagent` (see [Installation](../../README.md#installation)).


## Quick Start

Set the environment variables for your vision model:

```bash
export MODEL_ID="your-model-id"
export MODEL_BASE_URL="your-base-url"
export MODEL_API_KEY="your-api-key"
```

Run the agent:

```bash
python examples/react-vision/agent.py
```
