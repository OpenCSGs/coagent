# Streaming Ping-Pong

This example demonstrates how to handle streaming messages. The server sends a stream of pongs and the client receives and prints them.


## Quick Start

First, follow the instructions in [Prerequisites](../../README.md#prerequisites) and [Installation](../../README.md#installation).


### Using NATS Runtime

Start a server in one terminal:

```bash
python examples/stream-ping-pong/server.py
```

Then communicate with the agent in another terminal:

```bash
coagent stream_server -H type:Ping --chat
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
python examples/stream-ping-pong/server.py --server http://localhost:8000
```

Finally, start a client in another terminal.

```bash
coagent stream_server -H type:Ping --chat --server http://localhost:8000
```
