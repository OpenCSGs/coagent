# Agentic OpenCSG Demo


## Prerequisites

- Install `coagent` (see [Installation](../../README.md#installation)).
- Start a NATS server (see [Distributed](../../README.md#distributed)).


## Quick Start

### Run the Triage agent

Run the OpenCSG triage agent:

```bash
export AZURE_MODEL="your-model-name"
export AZURE_API_BASE="your-api-base"
export AZURE_API_VERSION="your-api-version"
export AZURE_API_KEY="your-api-key"

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
export AZURE_MODEL="your-model-name"
export AZURE_API_BASE="your-api-base"
export AZURE_API_VERSION="your-api-version"
export AZURE_API_KEY="your-api-key"

python examples/opencsg/csghub.py team1.csghub
```

Then search in the client terminal, then you will get a professional answer from CSGHub:

```bash
python examples/rich_client.py opencsg
Input: Search wukong-1b model
```
