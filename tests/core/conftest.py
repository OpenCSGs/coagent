from typing import Callable, Awaitable, AsyncIterator

import pytest

from coagent.core.types import Address, RawMessage, Channel, Subscription


class TestChannel(Channel):
    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def publish(
        self,
        addr: Address,
        msg: RawMessage,
        request: bool = False,
        reply: str = "",
        timeout: float = 0.5,
        probe: bool = True,
    ) -> RawMessage | None:
        pass

    async def publish_multi(
        self,
        addr: Address,
        msg: RawMessage,
        probe: bool = True,
    ) -> AsyncIterator[RawMessage]:
        pass

    async def subscribe(
        self,
        addr: Address,
        handler: Callable[[RawMessage], Awaitable[None]],
        queue: str = "",
    ) -> Subscription:
        pass

    async def new_reply_topic(self) -> str:
        pass


@pytest.fixture
def test_channel() -> TestChannel:
    return TestChannel()
