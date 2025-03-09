# Integration with AutoGen

This example demonstrates how to integrate [AutoGen's AgentChat][1] into Coagent.

References:

- [AgentChat Quickstart][2]
- [Extend Power of AutoGen with Promptflow][3]


## Prerequisites

- Install `coagent` (see [Installation](../../README.md#installation)).
- Start a NATS server (see [Distributed](../../README.md#distributed)).
- Install `autogen-agentchat` and `autogen-ext`:

    ```bash
    pip install 'autogen-agentchat==0.4.0.dev6'
    pip install 'autogen-ext[openai,azure]==0.4.0.dev6'
    ```


## Quick Start

First, start a server in one terminal:

```bash
export MODEL_ID="your-model-id"
export MODEL_BASE_URL="your-base-url"
export MODEL_API_VERSION="your-api-version"
export MODEL_API_KEY="your-api-key"

python examples/framework-integration/autogen/agent.py
```

Then communicate with the agent using the `coagent` CLI:

```bash
coagent agent -H type:ChatMessage --chat -d '{"role":"user","content":"What is the weather like in Beijing?"}'
```


[1]: https://microsoft.github.io/autogen/0.4.0.dev6/user-guide/agentchat-user-guide/index.html
[2]: https://microsoft.github.io/autogen/0.4.0.dev6/user-guide/agentchat-user-guide/quickstart.html
[3]: https://techcommunity.microsoft.com/blog/azure-ai-services-blog/extend-power-of-autogen-with-promptflow/4113829
