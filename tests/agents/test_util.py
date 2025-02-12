import pytest

from coagent.agents.util import chat


@pytest.mark.asyncio
async def test_chat(mock_model_client):
    response = await chat(
        messages=[],
        stream=False,
        client=mock_model_client,
    )
    assert response.content == "hello"


@pytest.mark.asyncio
async def test_chat_stream(mock_model_client):
    response = await chat(
        messages=[],
        stream=True,
        client=mock_model_client,
    )
    chunk = None
    async for _chunk in response:
        # Only one chunk.
        chunk = _chunk
    assert chunk and chunk.content == "hello"
