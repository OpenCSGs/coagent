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

Then start a client in another terminal.

```bash
python examples/discovery/client.py team1
```
