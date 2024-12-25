# CoS Example


## Quick Start

First, follow the instructions in [Prerequisites](../../README.md#prerequisites) and [Installation](../../README.md#installation).


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
python examples/ping-pong/client.py
```

or start a stream-ping-pong client:

```bash
python examples/stream-ping-pong/client.py
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
python examples/ping-pong/client.py
```

or start a stream-ping-pong client:

```bash
python examples/stream-ping-pong/client.py
```

### Run Go Agent

Build Go agent:

```bash
cd examples/cos/goagent
go build
```

Run a Go agent in one terminal:

```bash
cd examples/cos/goagent
./goagent
```
