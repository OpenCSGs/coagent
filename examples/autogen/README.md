# Using AutoGen

This example demonstrates how to use [AutoGen's AgentChat][1] in Coagent.

References:

- [AgentChat Quickstart][2]
- [Extend Power of AutoGen with Promptflow][3]


## Quick Start

First, follow the instructions in [Prerequisites](../../README.md#prerequisites) and [Installation](../../README.md#installation).

Also need to install the following package and extension:

```bash
pip install 'autogen-agentchat==0.4.0.dev6'
pip install 'autogen-ext[openai,azure]==0.4.0.dev6'
```

Then start a server in one terminal:

```bash
export AZURE_MODEL=csg-gpt4
export AZURE_API_BASE=https://opencsg-us.openai.azure.com
export AZURE_API_VERSION=2024-02-15-preview
export AZURE_API_KEY=<YOUR API KEY>

python examples/using-autogen/autogen.py
```

Finally, start a client in another terminal.

```bash
python examples/rich_client.py autogen
```


[1]: https://microsoft.github.io/autogen/0.4.0.dev6/user-guide/agentchat-user-guide/index.html
[2]: https://microsoft.github.io/autogen/0.4.0.dev6/user-guide/agentchat-user-guide/quickstart.html
[3]: https://techcommunity.microsoft.com/blog/azure-ai-services-blog/extend-power-of-autogen-with-promptflow/4113829
