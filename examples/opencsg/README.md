# Agentic OpenCSG Demo


## Quick Start

First, follow the instructions in [Prerequisites](../../README.md#prerequisites) and [Installation](../../README.md#installation).

### Run the Triage agent

Run the OpenCSG triage agent:

```bash
export AZURE_MODEL=csg-gpt4
export AZURE_API_BASE=https://opencsg-us.openai.azure.com
export AZURE_API_VERSION=2024-02-15-preview
export AZURE_API_KEY=<YOUR API KEY>

python examples/opencsg/opencsg.py team1
```

Then start a client in another terminal:

```bash
python examples/rich_client.py opencsg
Input: Search wukong-1b model
```

You will not get any useful information since the triage agent itself has no knowledge of the OpenCSG's models.

### Add the CSGHub agent

Run the CSGHub agent:

```bash
export AZURE_MODEL=csg-gpt4
export AZURE_API_BASE=https://opencsg-us.openai.azure.com
export AZURE_API_VERSION=2024-02-15-preview
export AZURE_API_KEY=<YOUR API KEY>

python examples/opencsg/csghub.py team1.csghub
```

Then search in the client terminal and you will get a professional answer from CSGHub:

```bash
python examples/rich_client.py opencsg
Input: Search wukong-1b model
```
