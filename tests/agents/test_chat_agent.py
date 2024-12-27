from pydantic import Field
import pytest

from coagent.agents.chat_agent import wrap_error


@pytest.mark.asyncio
async def test_wrap_error():
    @wrap_error
    async def func(
        a: int = Field(..., description="Argument a"),
        b: int = Field(1, description="Argument b"),
    ) -> float:
        return a / b

    assert await func() == "Error: Missing required argument 'a'"
    assert await func(a=1) == 1
    assert await func(a=1, b=0) == "Error: division by zero"
