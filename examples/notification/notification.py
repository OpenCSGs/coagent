import asyncio
from typing import AsyncIterator

from coagent.core import (
    Address,
    AgentSpec,
    BaseAgent,
    Context,
    handler,
    idle_loop,
    logger,
    Message,
    new,
    set_stderr_logger,
)
from coagent.core.messages import ControlMessage
from coagent.runtimes import NATSRuntime


class Notification(Message):
    type: str
    content: str


class Subscribe(Message):
    user_id: str


class Notify(Message):
    user_id: str
    notification: Notification


class _SubscribeToCenter(Message):
    user_id: str
    sender: Address


class _UnsubscribeFromCenter(Message):
    user_id: str


class _ControlNotify(ControlMessage):
    """A CONTROL message for putting a notification into the queue."""

    notification: Notification


class Proxy(BaseAgent):
    """A proxy agent that accepts subscriptions from the user and forwards the
    notifications from the singleton center agent to the user.
    """

    def __init__(self):
        # The agent is long-running and will be deleted when the user cancels.
        super().__init__(timeout=float("inf"))

        self.__queue: asyncio.Queue[Notification] = asyncio.Queue()

    @handler
    async def notify(self, msg: _ControlNotify, ctx: Context) -> None:
        await self.__queue.put(msg.notification)

    @handler
    async def subscribe(
        self, msg: Subscribe, ctx: Context
    ) -> AsyncIterator[Notification]:
        # Subscribe to the singleton center agent.
        await self.channel.publish(
            Center.SINGLETON_ADDRESS,
            _SubscribeToCenter(user_id=msg.user_id, sender=self.address).encode(),
        )

        while True:
            try:
                # Forward notifications from the center agent to the user.
                notification = await self.__queue.get()
                self.__queue.task_done()
                yield notification
            except asyncio.CancelledError:
                # Unsubscribe from the center agent when the user cancelled.
                await self.channel.publish(
                    Center.SINGLETON_ADDRESS,
                    _UnsubscribeFromCenter(user_id=msg.user_id).encode(),
                )
                raise


class Center(BaseAgent):
    """A center agent that listens to notifications and forwards them to the
    appropriate subscribing agents.
    """

    SINGLETON_ADDRESS = Address(name="center", id="singleton")

    def __init__(self):
        # This is a long-running agent and has the same lifetime as the application.
        super().__init__(timeout=float("inf"))

        self.__subscribers: dict[str, Address] = {}

    @handler
    async def subscribe(self, msg: _SubscribeToCenter, ctx: Context) -> None:
        self.__subscribers[msg.user_id] = msg.sender
        logger.info(f"User {msg.user_id} subscribed")

    @handler
    async def unsubscribe(self, msg: _UnsubscribeFromCenter, ctx: Context) -> None:
        self.__subscribers.pop(msg.user_id, None)
        logger.info(f"User {msg.user_id} unsubscribed")

    @handler
    async def notify(self, msg: Notify, ctx: Context) -> None:
        addr = self.__subscribers.get(msg.user_id)
        if not addr:
            logger.warning(f"User {msg.user_id} is not subscribed")
            return

        _notify = _ControlNotify(notification=msg.notification)
        await self.channel.publish(addr, _notify.encode())
        logger.info(f"Notification sent to user {msg.user_id}")


proxy = AgentSpec("proxy", new(Proxy))
center = AgentSpec("center", new(Center))


async def main():
    async with NATSRuntime.from_servers() as runtime:
        await runtime.register(proxy)
        await runtime.register(center)
        await idle_loop()


if __name__ == "__main__":
    set_stderr_logger()
    asyncio.run(main())
