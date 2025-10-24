from dataclasses import dataclass
from typing import Literal, TypeAlias, Union


@dataclass
class MCPToolChoice:
    server_label: str
    name: str


ToolChoice: TypeAlias = Union[
    Literal["auto", "required", "none"], str, MCPToolChoice, None
]


@dataclass
class ModelSettings:
    """Settings to use when calling an LLM.

    This class holds optional model configuration parameters (e.g. temperature,
    top_p, penalties, truncation, etc.).

    Not all models/providers support all of these parameters, so please check the API documentation
    for the specific model and provider you are using.
    """

    temperature: float | None = None
    """The temperature to use when calling the model."""

    top_p: float | None = None
    """The top_p to use when calling the model."""

    frequency_penalty: float | None = None
    """The frequency penalty to use when calling the model."""

    presence_penalty: float | None = None
    """The presence penalty to use when calling the model."""

    tool_choice: ToolChoice | None = None
    """The tool choice to use when calling the model."""

    parallel_tool_calls: bool | None = None
    """Controls whether the model can make multiple parallel tool calls in a single turn.
    If not provided (i.e., set to None), this behavior defers to the underlying
    model provider's default. For most current providers (e.g., OpenAI), this typically
    means parallel tool calls are enabled (True).
    Set to True to explicitly enable parallel tool calls, or False to restrict the
    model to at most one tool call per turn.
    """
