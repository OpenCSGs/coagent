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


def test_function_to_jsonschema_no_description():
    def func(a: int, b: str = "ok", c: float = None) -> None:
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
                    "c": {"default": None, "title": "C", "type": "number"},
                },
                "required": ["a"],
                "title": "func",
                "type": "object",
            },
        },
        "type": "function",
    }


def test_function_to_jsonschema_annotated_with_string():
    def func(
        a: Annotated[int, "The description for parameter a"],
        b: Annotated[str, "The description for parameter b"] = "ok",
        c: Annotated[float, "The description for parameter c"] = None,
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
                    "a": {
                        "description": "The description for parameter a",
                        "title": "A",
                        "type": "integer",
                    },
                    "b": {
                        "default": "ok",
                        "description": "The description for parameter b",
                        "title": "B",
                        "type": "string",
                    },
                    "c": {
                        "default": None,
                        "description": "The description for parameter c",
                        "title": "C",
                        "type": "number",
                    },
                },
                "required": ["a"],
                "title": "func",
                "type": "object",
            },
        },
        "type": "function",
    }


def test_function_to_jsonschema_annotated_with_pydantic_field():
    def func(
        a: Annotated[int, Field(description="The description for parameter a")],
        b: Annotated[str, Field(description="The description for parameter b")] = "ok",
        c: Annotated[
            float, Field(description="The description for parameter c")
        ] = None,
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
                    "a": {
                        "description": "The description for parameter a",
                        "title": "A",
                        "type": "integer",
                    },
                    "b": {
                        "default": "ok",
                        "description": "The description for parameter b",
                        "title": "B",
                        "type": "string",
                    },
                    "c": {
                        "default": None,
                        "description": "The description for parameter c",
                        "title": "C",
                        "type": "number",
                    },
                },
                "required": ["a"],
                "title": "func",
                "type": "object",
            },
        },
        "type": "function",
    }


def test_function_to_jsonschema_default_to_pydantic_field():
    def func(
        a: int = Field(description="The description for parameter a"),
        b: str = Field(default="ok", description="The description for parameter b"),
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
                    "a": {
                        "description": "The description for parameter a",
                        "title": "A",
                        "type": "integer",
                    },
                    "b": {
                        "default": "ok",
                        "description": "The description for parameter b",
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
