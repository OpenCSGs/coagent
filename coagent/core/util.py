import asyncio
import os
import signal
from typing import Any, get_type_hints

import pygtrie

from .logger import logger


class Trie(pygtrie.StringTrie):
    EMPTY = pygtrie._EMPTY

    def direct_items(self, prefix: str) -> list[tuple[str, Any]]:
        """Return items directly under the given prefix."""

        max_level: int = len(prefix.split(self._separator)) if prefix else 0
        items: list[tuple[str, Any]] = []

        def traverse_callback(path_conv, path, children, value=None):
            key = path_conv(path)
            if key.startswith(prefix):
                items.append((key, value))

            if len(path) <= max_level:
                # Traverse into the children of the current node.
                list(children)

        self.traverse(traverse_callback)
        return items

    def direct_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        for key, _ in self.direct_items(prefix):
            keys.append(key)
        return keys

    def direct_values(self, prefix: str) -> list[Any]:
        values: list[Any] = []
        for _, value in self.direct_items(prefix):
            values.append(value)
        return values


def get_func_args(func) -> set[str]:
    if hasattr(func, "__mcp_tool_args__"):
        return set(func.__mcp_tool_args__)

    hints = get_type_hints(func)
    hints.pop("return", None)  # Ignore the return type.
    return set(hints.keys())


async def clear_queue(queue: asyncio.Queue) -> None:
    """Clear the given queue."""

    # Drain all the remaining items in the queue.
    #
    # We can change to `queue.shutdown(immediate=True)` in Python 3.13+
    while not queue.empty():
        try:
            queue.get_nowait()
            queue.task_done()
        except asyncio.QueueEmpty:
            break


async def idle_loop():
    try:
        stop_event = asyncio.Event()

        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, stop_event.set)

        while not stop_event.is_set():
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        pass


def exit_loop():
    os.kill(os.getpid(), signal.SIGINT)


def pretty_trace_agent_output(name: str, content: str):
    logger.opt(colors=True).trace(
        f"<green>{name}</green> =>\n\n<magenta>{content}</magenta>"
    )


def pretty_trace_tool_call(name: str, args: dict[str, any]):
    args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
    logger.opt(colors=True).trace(
        f"<green>{name}</green><magenta>({args_str})</magenta>"
    )
