# Agent Discovery


## Prerequisites

- Install `coagent` (see [Installation](../../README.md#installation)).
- Start a NATS server (see [Distributed](../../README.md#distributed)).


## Quick Start

First, start different servers in separate terminals:

```bash
python examples/discovery/server.py team1.dev "Dev Engineer in Team 1."
```

```bash
python examples/discovery/server.py team1.qa "QA Engineer in Team 1."
```

```bash
python examples/discovery/server.py team2.dev "Dev Engineer in Team 2."
```

```bash
python examples/discovery/server.py team3.qa "QA Engineer in Team 3."
```

Then discover the available agent types using the `coagent` CLI:

```bash
coagent discovery -H type:DiscoveryQuery -F .content.agents -d '{"namespace":"team1"}'
```

Or start a more-friendly client in another terminal:

```bash
python examples/discovery/client.py --namespace team1
```
