# Coagent

An experimental agent framework.


<p align="center">
<img src="assets/coagent-overview.png" height="600">
</p>


## Features

- [x] Event-driven
- [x] Distributed & Fault-tolerant
- [x] Single-agent
    - [x] Function-calling
    - [ ] ReAct
- [x] Multi-agent orchestration
    - [x] Agent Discovery
    - [x] Static orchestration
        - [x] Sequential
    - [x] Dynamic orchestration
        - [x] Dynamic Triage
        - [x] Handoffs (based on async Swarm)
        - [ ] Group Chat
- [x] Runtime
    - [x] NATSRuntime (NATS-based Distributed Runtime)
        - [ ] Using NATS [JetStream][2]
    - [x] HTTPRuntime (HTTP-based Distributed Runtime)
    - [x] LocalRuntime (In-process Runtime)
- [x] [CoS](coagent/cos) (Multi-language support)
    - [x] [Python](examples/cos/cos.py)
    - [x] [Node.js](examples/cos/cos.js)
    - [x] [Go](examples/cos/goagent)
    - [ ] Rust
- [ ] Cross-language support
    - [ ] Protocol Buffers


## Three-tier Architecture

<p align="center">
<img src="assets/coagent-three-tier-architecture.png" height="500">
</p>


## Prerequisites

Start a NATS server ([docs][1]):

```bash
docker run -p 4222:4222 --name nats-server -ti nats:latest
```


## Installation

```bash
pip install git+https://github.com/OpenCSGs/coagent.git
```


## Quick Start

### Simple Agent

Create a Ping-pong agent:

```python
# server.py

import asyncio

from coagent.core import (
    BaseAgent,
    Context,
    handler,
    idle_loop,
    Message,
    new,
)
from coagent.runtimes import NATSRuntime


class Ping(Message):
    pass


class Pong(Message):
    pass


class Server(BaseAgent):
    """The Ping-pong agent."""

    @handler
    async def handle(self, msg: Ping, ctx: Context) -> Pong:
        """Handle the Ping message and return a Pong message."""
        return Pong()


async def main():
    async with NATSRuntime.from_servers("nats://localhost:4222") as runtime:
        await runtime.register("server", new(Server))
        await idle_loop()


if __name__ == "__main__":
    asyncio.run(main())
```

Run the agent:

```bash
python server.py
```

Communicate with the agent:

```bash
coagent server -H type:Ping
```

### LLM-based Agent

Create a Translator agent:

```python
# translator.py

import asyncio
import os

from coagent.agents import ChatAgent, ModelClient
from coagent.core import idle_loop, new, set_stderr_logger
from coagent.runtimes import NATSRuntime


class Translator(ChatAgent):
    """The translator agent."""

    system="You are a professional translator that can translate Chinese to English."

    client = ModelClient(
        model=os.getenv("MODEL_NAME"),
        api_base=os.getenv("MODEL_API_BASE"),
        api_version=os.getenv("MODEL_API_VERSION"),
        api_key=os.getenv("MODEL_API_KEY"),
    )


async def main():
    async with NATSRuntime.from_servers("nats://localhost:4222") as runtime:
        await runtime.register("translator", new(Translator))
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger("TRACE")
    asyncio.run(main())
```

Run the agent:

```bash
export MODEL_NAME=<YOUR_MODEL_NAME>
export MODEL_API_BASE=<YOUR_MODEL_API_BASE>
export MODEL_API_VERSION=<YOUR_MODEL_API_VERSION>
export MODEL_API_KEY=<YOUR_MODEL_API_KEY>
python translator.py
```

Communicate with the agent:

```bash
coagent translator -H type:ChatHistory -d '{"messages":[{"role":"user","content":"你好"}]}' --stream -F '.content.content' --oneline
```


## Examples

- [ping-pong](examples/ping-pong)
- [stream-ping-pong](examples/stream-ping-pong)
- [discovery](examples/discovery)
- [translator](examples/translator)
- [opencsg](examples/opencsg)
- [app-builder](examples/app-builder)
- [autogen](examples/autogen)
- [cos](examples/cos)



[1]: https://docs.nats.io/running-a-nats-service/nats_docker/nats-docker-tutorial
[2]: https://docs.nats.io/nats-concepts/jetstream
