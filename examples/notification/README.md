# Notification Center

This example demonstrates how to implement a notification center to send and receive notifications.


## Prerequisites

- Install `coagent` (see [Installation](../../README.md#installation)).
- Start a NATS server (see [Distributed](../../README.md#distributed)).


## Quick Start

### Using NATS Runtime

Start a notification center in one terminal:

```bash
python examples/notification/notification.py
```

Then create a subscription via a proxy agent in another terminal:

```bash
coagent proxy -H type:Subscribe --stream --filter .content -d '{"user_id": "1"}'
```

Finally, send a notification to the center agent in a third terminal, and then observe the output in the second terminal:

```bash
coagent center:singleton -H type:Notify -d '{"user_id": "1", "notification": {"type": "created", "content": "Hello, world!"}}'
```
