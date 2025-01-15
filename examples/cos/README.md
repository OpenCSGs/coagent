# CoS Example


## Prerequisites

- Install `coagent` (see [Installation](../../README.md#installation)).
- Start a NATS server (see [Distributed](../../README.md#distributed)).


## Quick Start

### Run Node.js Agent

Start the CoS server in one terminal:

```bash
python coagent/cos/app.py
```

Then run a Node.js agent in another terminal:

```bash
node examples/cos/cos.js
```

Finally, start a ping-pong client in the third terminal:

```bash
coagent server -H type:Ping
```

or start a stream-ping-pong client:

```bash
coagent stream_server -H type:Ping --chat
```


### Run Python Agent

Start the CoS server in one terminal:

```bash
python coagent/cos/app.py
```

Then run a Python agent in another terminal:

```bash
python examples/cos/cos.py
```

Finally, start a ping-pong client in the third terminal:

```bash
coagent server -H type:Ping
```

or start a stream-ping-pong client:

```bash
coagent stream_server -H type:Ping --chat
```

### Run Go Agent

Start the CoS server in one terminal:

```bash
python coagent/cos/app.py
```

Then build and run the Go agent:

```bash
cd examples/cos/goagent
go build
./goagent
```

Finally, start a ping-pong client in the third terminal:

```bash
coagent server -H type:Ping
```
