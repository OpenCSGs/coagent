# Streaming Ping-Pong

This example demonstrates how to handle streaming messages. The server sends a stream of pongs and the client receives and prints them.


## Quick Start

First, follow the instructions in [Prerequisites](../../README.md#prerequisites) and [Installation](../../README.md#installation).


### Using NATS Runtime

Start a server in one terminal:

```bash
python examples/stream-ping-pong/server.py
```

Finally, start a client in another terminal.

```bash
python examples/stream-ping-pong/client.py
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
python examples/stream-ping-pong/client.py --server http://localhost:8000
```

or mimic the client behavior by using cURL:

```bash
curl -N -XPOST http://localhost:8000/publish_multi \
  -H 'Content-Type: application/json' \
  -d '{
  "addr": {
    "name": "stream_server",
    "id": "e6516e77a4cc442796e05f3ebff0b367"
  },  
  "msg": {
    "header": {
      "type": "Ping"
    }
  }  
}'
```
