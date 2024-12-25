import os

from openai import AsyncAzureOpenAI
from pydantic import BaseModel, Field


class ModelClient(BaseModel):
    model: str = Field(os.getenv("AZURE_MODEL", ""), description="The model name.")
    api_base: str = Field("", description="The API base URL.")
    api_version: str = Field("", description="The API version.")
    api_key: str = Field("", description="The API key.")

    @property
    def azure_client(self) -> AsyncAzureOpenAI:
        return AsyncAzureOpenAI(
            azure_endpoint=self.api_base or os.getenv("AZURE_API_BASE"),
            api_version=self.api_version or os.getenv("AZURE_API_VERSION"),
            api_key=self.api_key or os.getenv("AZURE_API_KEY"),
        )


default_model_client = ModelClient()
