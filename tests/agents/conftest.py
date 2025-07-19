import pytest

from coagent.agents.model import Model


class MockModel(Model):
    async def acompletion(
        self,
        messages: list[dict],
        model: str = "",
        stream: bool = False,
        temperature: float = 0.1,
        tools: list | None = None,
        tool_choice: str | None = None,
        response_format: dict | None = None,
        **kwargs,
    ):  # -> litellm.ModelResponse:
        if stream:
            return self._stream_response()
        else:
            return await self._non_stream_response()

    async def _non_stream_response(self):
        import litellm
        from litellm.types.utils import Choices, Message

        return litellm.ModelResponse(
            choices=[Choices(message=Message(content="hello"))]
        )

    async def _stream_response(self):
        import litellm
        from litellm.types.utils import StreamingChoices, Delta

        yield litellm.ModelResponse(
            choices=[StreamingChoices(delta=Delta(content="hello"))]
        )


@pytest.fixture
def mock_model() -> Model:
    return MockModel(id="mock_model")
