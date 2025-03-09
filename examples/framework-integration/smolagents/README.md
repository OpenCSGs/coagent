# Using AutoGen

This example demonstrates how to use [smolagents' ToolCallingAgent][1] in Coagent.

References:

- [Agent from any LLM][2]


## Prerequisites

- Install `coagent` (see [Installation](../../README.md#installation)).
- Start a NATS server (see [Distributed](../../README.md#distributed)).
- Install `smolagents`:

    ```bash
    pip install smolagents
    ```


## Quick Start

First, start a server in one terminal:

```bash
export MODEL_ID="your-model-id"
export MODEL_BASE_URL="your-base-url"
export MODEL_API_KEY="your-api-key"

python examples/framework-integration/smolagents/agent.py
```

Then communicate with the agent using the `coagent` CLI:

```bash
coagent agent -H type:ChatMessage --chat -d '{"role":"user","content":"What is the weather like in Beijing?"}'
```


[1]: https://huggingface.co/docs/smolagents/reference/agents#smolagents.ToolCallingAgent
[2]: https://github.com/huggingface/smolagents/blob/main/examples/agent_from_any_llm.py
