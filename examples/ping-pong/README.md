# Ping-Pong


## Quick Start

First, follow the instructions in [Prerequisites](../../README.md#prerequisites) and [Installation](../../README.md#installation).


### Using NATS Runtime

Start a server in one terminal:

```bash
python examples/ping-pong/server.py
```

Finally, start a client in another terminal.

```bash
python examples/ping-pong/client.py
```


### Using HTTP Runtime

Install the following packages:

```bash
pip install hypercorn
pip install starlette
pip install sse-starlette
```

Start the HTTP runtime server:

```bash
python examples/ping-pong/http_runtime_server.py
```

Then start a server in one terminal:

```bash
python examples/ping-pong/server.py --server http://localhost:8000
```

Finally, start a client in another terminal.

```bash
python examples/ping-pong/client.py --server http://localhost:8000
```
