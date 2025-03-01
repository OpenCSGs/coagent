from typing import AsyncIterator

from pydantic import Field
import pytest

from coagent.agents.chat_agent import wrap_error


@pytest.mark.asyncio
async def test_wrap_error_normal():
    @wrap_error
    async def func(
        a: int = Field(..., description="Argument a"),
        b: int = Field(1, description="Argument b"),
    ) -> float:
        return a / b

    assert await func() == "Error: Missing required argument 'a'"
    assert await func(a=1) == 1
    assert await func(a=1, b=0) == "Error: division by zero"


@pytest.mark.asyncio
async def test_wrap_error_aiter():
    @wrap_error
    async def func(
        a: int = Field(..., description="Argument a"),
        b: int = Field(1, description="Argument b"),
    ) -> AsyncIterator[float]:
        yield a / b

    result = await func()
    assert result == "Error: Missing required argument 'a'"

    result = await func(a=1)
    assert await anext(result) == 1

    result = await func(a=1, b=0)
    assert await anext(result) == "Error: division by zero"
