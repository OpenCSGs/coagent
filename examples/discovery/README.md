# Agent Discovery


## Quick Start

First, follow the instructions in [Prerequisites](../../README.md#prerequisites) and [Installation](../../README.md#installation).

Then start different servers in separate terminals:

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

Finally, start a client in another terminal.

```bash
python examples/discovery/client.py team1
```
