import inspect
from datetime import datetime
from typing import Any

from pydantic import Field, create_model
from pydantic.fields import FieldInfo

from coagent.agents.messages import ChatMessage

__CTX_VARS_NAME__ = "ctx"


def debug_print(debug: bool, *args: str) -> None:
    if not debug:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = " ".join(map(str, args))
    print(f"\033[97m[\033[90m{timestamp}\033[97m]\033[90m {message}\033[0m")


def merge_fields(target, source):
    for key, value in source.items():
        if isinstance(value, str):
            # A dirty workaround to avoid containing duplicate "function" in
            # the `type` field. (e.g. "functionfunction")
            if key == "type" and target[key] == "function":
                continue
            target[key] += value
        elif value is not None and isinstance(value, dict):
            merge_fields(target[key], value)


def merge_chunk(final_response: dict, delta: dict) -> None:
    delta.pop("role", None)
    merge_fields(final_response, delta)

    tool_calls = delta.get("tool_calls")
    if tool_calls and len(tool_calls) > 0:
        index = tool_calls[0].pop("index")
        merge_fields(final_response["tool_calls"][index], tool_calls[0])


def function_to_json(func) -> dict:
    """
    Converts a Python function into a JSON-serializable dictionary
    that describes the function's signature, including its name,
    description, and parameters.

    Args:
        func: The function to be converted.

    Returns:
        A dictionary representing the function's signature in JSON format.
    """
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null",
    }

    try:
        signature = inspect.signature(func)
    except ValueError as e:
        raise ValueError(
            f"Failed to get signature for function {func.__name__}: {str(e)}"
        )

    parameters = {}
    for param in signature.parameters.values():
        try:
            param_type = type_map.get(param.annotation, "string")
        except KeyError as e:
            raise KeyError(
                f"Unknown type annotation {param.annotation} for parameter {param.name}: {str(e)}"
            )
        parameters[param.name] = {"type": param_type}

    required = [
        param.name
        for param in signature.parameters.values()
        if param.default == inspect._empty
    ]

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": func.__doc__ or "",
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required,
            },
        },
    }


def function_to_jsonschema(func) -> dict:
    """
    Converts a function into a JSON Schema will be passed into Chat Completions `tools`.

    Note that most of the code is borrowed from
    https://github.com/MadcowD/ell/blob/82d626b52e5f7c72f29ecdc934e36beaaab258a3/src/ell/lmp/tool.py#L87-L119.

    ## Example

    Given the function in the following format:

    ```python
    def greet(name: str, age: int, location: str = "New York"):
        '''Greets the user. Make sure to get their name and age before calling.'''
    ```

    Rewrite it as below:

    ```python
    from pydantic import Field

    def greet(
        name: str = Field(description="The name of the person"),
        age: int = Field(description="The age of the person"),
        location: str = Field(default="New York", description="The location of the person"),
    ):
        '''Greets the user. Make sure to get their name and age before calling.'''
    ```

    Then you will get a JSON schema with per-parameter descriptions.
    """

    if hasattr(func, "__mcp_tool_schema__"):
        # If the function already has a schema, return it.
        # This is the case for tools used in MCPAgent.
        return dict(
            type="function",
            function=func.__mcp_tool_schema__
        )

    # Construct the pydantic mdoel for the _under_fn's function signature parameters.
    # 1. Get the function signature.

    sig = inspect.signature(func)

    # 2. Create a dictionary of field definitions for the Pydantic model
    fields = {}
    for param_name, param in sig.parameters.items():
        # Skip the special self argument.
        if param_name == "self":
            continue

        # Skip the special context argument.
        if param_name == __CTX_VARS_NAME__:
            continue

        # Skip *args and **kwargs
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        # Determine the type annotation
        if param.annotation == inspect.Parameter.empty:
            raise ValueError(
                f"Parameter {param_name} has no type annotation, and cannot be converted into a tool schema for OpenAI and other provisders. Should OpenAI produce a string or an integer, etc, for this parameter?"
            )
        annotation = param.annotation

        # Determine the default value
        default = param.default

        # Check if the parameter has a Field with description
        if isinstance(param.default, FieldInfo):
            field = param.default
            fields[param_name] = (annotation, field)
        elif param.default != inspect.Parameter.empty:
            fields[param_name] = (annotation, param.default)
        else:
            # If no default value, use Field without default
            fields[param_name] = (annotation, Field(...))

    # 3. Create the Pydantic model
    model_name = f"{func.__name__}"
    ParamsModel = create_model(model_name, **fields)
    return dict(
        type="function",
        function=dict(
            name=func.__name__,
            description=func.__doc__ or "",
            parameters=ParamsModel.model_json_schema(),
        ),
    )


def handoff(triage_agent, *agents, transfer_back: bool = True):
    """
    Transfer the conversation from triage_agent to candidate agents.

    Args:
        triage_agent: The agent that will transfer the conversation.
        agents: The candidate agents that might handle the conversation next.
    """

    def transfer_back_to_triage():
        """Call this if the user brings up a topic outside your purview, including escalating to human."""
        return triage_agent

    for agent in agents:
        transfer_to = lambda: agent
        transfer_to.__name__ = agent.name
        triage_agent.functions.append(transfer_to)

        if transfer_back:
            agent.functions.append(transfer_back_to_triage)


def normalize_function_result(result: Any) -> ChatMessage:
    if isinstance(result, ChatMessage):
        return result
    return ChatMessage(role="assistant", content=str(result))
