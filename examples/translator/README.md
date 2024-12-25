# Translator


## Quick Start

First, follow the instructions in [Prerequisites](../../README.md#prerequisites) and [Installation](../../README.md#installation).

Then start a server in one terminal:

```bash
export AZURE_MODEL=csg-gpt4
export AZURE_API_BASE=https://opencsg-us.openai.azure.com
export AZURE_API_VERSION=2024-02-15-preview
export AZURE_API_KEY=<YOUR API KEY>

python examples/translator/translator.py
```

Finally, communicate with the agent using the `coagent` CLI:

```bash
coagent translator -H type:ChatHistory -d '{"messages":[{"role":"user","content":"你好"}]}' --stream -F '.content.content' --oneline
```

or start a more-friendly rich client in another terminal.

```bash
python examples/rich_client.py translator
```
