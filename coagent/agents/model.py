import os

# Importing litellm is super slow, so we are using lazy import for now.
# See https://github.com/BerriAI/litellm/issues/7605.
#
# import litellm
from pydantic import BaseModel, Field


# class ModelResponse(litellm.ModelResponse):
#     pass


class Model(BaseModel):
    provider: str = Field("", description="The model provider.")
    id: str = Field(..., description="The model ID.")
    base_url: str = Field("", description="The base URL.")
    api_version: str = Field("", description="The API version.")
    api_key: str = Field("", description="The API key.")

    @property
    def llm_provider(self) -> str:
        if self.provider:
            return self.provider

        import litellm

        _, provider, _, _ = litellm.get_llm_provider(
            self.id,
            api_base=self.base_url or None,
        )
        return provider

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
    ):  # -> ModelResponse:
        import litellm

        model = model or self.id
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            stream=stream,
            temperature=temperature,
            tools=tools,
            tool_choice=tool_choice,
            api_base=self.base_url,
            api_version=self.api_version,
            api_key=self.api_key,
            response_format=response_format,
            **kwargs,
        )
        return response


default_model = Model(
    id=os.getenv("MODEL_ID", ""),
    base_url=os.getenv("MODEL_BASE_URL", ""),
    api_version=os.getenv("MODEL_API_VERSION", ""),
    api_key=os.getenv("MODEL_API_KEY", ""),
)


# For backwards compatibility.
ModelClient = Model
default_model_client = default_model
