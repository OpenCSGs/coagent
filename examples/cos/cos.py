import abc
import argparse
import asyncio
import json
from urllib.parse import urljoin
import signal
from typing import Any, Type

import httpx
from httpx_sse import aconnect_sse


class Channel:
    def __init__(self, base_url: str, auth: str = ""):
        self._base_url = base_url
        self._headers = {"Authorization": f"Bearer {auth}"} if auth else None

    async def publish(self, addr: dict, msg: dict) -> dict | None:
        data = dict(
            addr=addr,
            msg=msg,
        )
        async with httpx.AsyncClient() as client:
            url = urljoin(self._base_url, "/runtime/channel/publish")
            resp = await client.post(url, json=data, headers=self._headers)
            resp.raise_for_status()

            # TODO: Handle result.

    async def publish_multi(self, addr: dict, handler) -> None:
        pass

    async def subscribe(self, path: str, data: dict, handler):
        async with httpx.AsyncClient(timeout=None) as client:
            async with aconnect_sse(
                client,
                "POST",
                urljoin(self._base_url, path),
                json=data,
                headers=self._headers or {},
            ) as event_source:
                async for sse in event_source.aiter_sse():
                    data_str = sse.data
                    data = json.loads(data_str)
                    await handler(data)

    async def request(self, path: str, data: dict) -> dict | None:
        pass


class Runtime:
    def __init__(self, base_url: str, auth: str = ""):
        self._channel = Channel(base_url, auth)
        self._factories: dict[str, Type] = {}

    async def register(self, name: str, constructor: Type, description: str = ""):
        if name in self._factories:
            raise ValueError(f"Agent {name} already registered")
        self._factories[name] = constructor

        data = dict(
            name=name,
            description=description,
        )
        coro = self._channel.subscribe("/runtime/register", data, self.handle)
        _ = asyncio.create_task(coro)

    async def handle(self, data: dict):
        match data["header"]["type"]:
            case "AgentCreated":
                await self.create_agent(data)
            case "AgentDeleted":
                await self.delete_agent(data)

    async def create_agent(self, data: dict):
        addr = json.loads(data["content"])["addr"]
        constructor = self._factories[addr["name"]]

        print(f"Creating agent with addr: {addr}")
        agent = constructor(self._channel, addr)
        coro = self._channel.subscribe(
            "runtime/channel/subscribe", dict(addr=addr), agent.receive
        )
        _ = asyncio.create_task(coro)

    async def delete_agent(self, data: dict):
        pass


async def idle_loop():
    try:
        stop_event = asyncio.Event()

        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, stop_event.set)

        while not stop_event.is_set():
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        pass


class Agent(abc.ABC):
    def __init__(self, channel: Channel, addr: dict):
        self.channel = channel
        self.addr = addr

    async def receive(self, msg: dict) -> None:
        print(f"Received a message: {msg}")

        result = self.handle(msg)

        reply = msg.get("reply") or {}
        reply_addr = reply.get("address")
        if not reply_addr:
            return

        if is_async_iterator(result):
            async for x in result:
                await self.channel.publish(reply_addr, x)
            # End of the iteration, send an extra StopIteration message.
            stop = {"header": {"type": "StopIteration"}}
            await self.channel.publish(reply_addr, stop)
        else:
            x = await result
            await self.channel.publish(reply_addr, x)

    @abc.abstractmethod
    async def handle(self, msg: dict) -> Any:
        pass


def is_async_iterator(obj) -> bool:
    """Check if obj is an async-iterator."""
    return hasattr(obj, "__aiter__") and hasattr(obj, "__anext__")


class Server(Agent):
    async def handle(self, msg: dict) -> Any:
        return {"header": {"type": "Pong"}}


class StreamServer(Agent):
    async def handle(self, msg: dict) -> Any:
        words = ("Hi ", "there, ", "this ", "is ", "the ", "Pong ", "server.")
        for word in words:
            await asyncio.sleep(0.6)
            yield {
                "header": {"type": "PartialPong"},
                "content": json.dumps({"content": word}),
            }


async def main(base_url: str, auth: str):
    runtime = Runtime(base_url, auth)
    await runtime.register("server", Server)
    await runtime.register("stream_server", StreamServer)
    await idle_loop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=str, default="http://127.0.0.1:8000")
    parser.add_argument("--auth", type=str, default="")
    args = parser.parse_args()

    asyncio.run(main(args.server, args.auth))
