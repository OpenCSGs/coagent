# Structured Outputs

This example demonstrates how to enable structured outputs when chatting with an agent. As a comparison, please also refer to the [original example from Ollama][1].

To learn more about structured outputs, see [OpenAI's Structured Outputs][2].


## Prerequisites

- Install `coagent` (see [Installation](../../README.md#installation)).
- Start a NATS server (see [Distributed](../../README.md#distributed)).


## Quick Start

Run [llama3.1][3] by using [Ollama][4]:

```bash
ollama run llama3.1
```

### Run the local agent

Run the agent as a script:

```bash
python examples/structured-outputs/local_agent.py
```

### Run the daemon agent

Run the agent as a daemon:

```bash
python examples/structured-outputs/daemon_agent.py
```

Then communicate with the agent using the `coagent` CLI:

```bash
coagent structured -H type:StructuredOutput --chat -d '{
  "input": {
    "role": "user",
    "content": "I have two friends. The first is Ollama 22 years old busy saving the world, and the second is Alonso 23 years old and wants to hang out. Return a list of friends in JSON format"
  },
  "output_schema": {
    "type": "json_schema",
    "json_schema": {
      "name": "FriendList",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "friends": {
            "items": {
              "$ref": "#/$defs/FriendInfo"
            },
            "type": "array"
          }
        },
        "required": [
          "friends"
        ],
        "$defs": {
          "FriendInfo": {
            "type": "object",
            "properties": {
              "name": {
                "type": "string"
              },
              "age": {
                "type": "integer"
              },
              "is_available": {
                "type": "boolean"
              }
            },
            "required": [
              "name",
              "age",
              "is_available"
            ]
          }
        }
      }
    }
  }
}'
```

[1]: https://github.com/ollama/ollama/blob/main/docs/openai.md#structured-outputs
[2]: https://platform.openai.com/docs/guides/structured-outputs
[3]: https://ollama.com/library/llama3.1
[4]: https://github.com/ollama/ollama
