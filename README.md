# Coagent

An experimental agent framework.


<p align="center">
<img src="assets/coagent-overview.png" height="800">
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
        - [x] Handoffs (Temporary support)
        - [ ] Group Chat
- [x] Runtime
    - [x] NATSRuntime (NATS-based Distributed Runtime)
        - [ ] Using NATS [JetStream][2]
    - [x] HTTPRuntime (HTTP-based Distributed Runtime)
    - [x] LocalRuntime (In-process Runtime)
- [x] Multi-language support
    - [x] [CoS (Coagent as a Service)](coagent/cos)
    - [x] Python
    - [ ] Go
    - [ ] Rust (Edge/Cloud Native)
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
poetry install
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
