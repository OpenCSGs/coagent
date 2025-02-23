from typing import Annotated

import pytest

from coagent.agents.util import chat
from coagent.agents.aswarm.util import function_to_jsonschema
from pydantic import Field


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


def test_function_to_jsonschema_normal():
    def func(a: int, b: str = "ok") -> None:
        """This is a test function."""
        pass

    schema = function_to_jsonschema(func)
    assert schema == {
        "function": {
            "description": "This is a test function.",
            "name": "func",
            "parameters": {
                "properties": {
                    "a": {"title": "A", "type": "integer"},
                    "b": {"default": "ok", "title": "B", "type": "string"},
                },
                "required": ["a"],
                "title": "func",
                "type": "object",
            },
        },
        "type": "function",
    }


def test_function_to_jsonschema_annotated():
    def func(a: Annotated[int, "Param a"], b: Annotated[str, "Param b"] = "ok") -> None:
        """This is a test function."""
        pass

    schema = function_to_jsonschema(func)
    assert schema == {
        "function": {
            "description": "This is a test function.",
            "name": "func",
            "parameters": {
                "properties": {
                    "a": {"description": "Param a", "title": "A", "type": "integer"},
                    "b": {
                        "default": "ok",
                        "description": "Param b",
                        "title": "B",
                        "type": "string",
                    },
                },
                "required": ["a"],
                "title": "func",
                "type": "object",
            },
        },
        "type": "function",
    }


def test_function_to_jsonschema_pydantic_field():
    def func(
        a: int = Field(description="Param a"),
        b: str = Field(default="ok", description="Param b"),
    ) -> None:
        """This is a test function."""
        pass

    schema = function_to_jsonschema(func)
    assert schema == {
        "function": {
            "description": "This is a test function.",
            "name": "func",
            "parameters": {
                "properties": {
                    "a": {"description": "Param a", "title": "A", "type": "integer"},
                    "b": {
                        "default": "ok",
                        "description": "Param b",
                        "title": "B",
                        "type": "string",
                    },
                },
                "required": ["a"],
                "title": "func",
                "type": "object",
            },
        },
        "type": "function",
    }
