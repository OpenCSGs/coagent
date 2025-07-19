# Standard library imports
import copy
import json
from collections import defaultdict
from typing import Any, AsyncIterator, List, Callable, Union

# Package/library imports
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import Choice, ChoiceDelta
from coagent.agents.messages import ChatMessage
from coagent.agents.model import Model
from coagent.core.agent import is_async_iterator
from coagent.core.util import get_func_args, pretty_trace_tool_call


# Local imports
from .util import (
    function_to_jsonschema,
    debug_print,
    merge_chunk,
    __CTX_VARS_NAME__,
    normalize_function_result,
)
from .types import (
    Agent,
    AgentFunction,
    ChatCompletionMessage,
    ChatCompletionMessageToolCall,
    Function,
    Response,
    Result,
)


class Swarm:
    def __init__(self, model: Model):
        self.model: Model = model

    async def get_chat_completion(
        self,
        agent: Agent,
        history: List,
        context_variables: dict,
        model_override: str,
        stream: bool,
        debug: bool,
        response_format: dict | None = None,
    ) -> ChatCompletionMessage:
        context_variables = defaultdict(str, context_variables)
        instructions = (
            agent.instructions(context_variables)
            if callable(agent.instructions)
            else agent.instructions
        )
        messages = [{"role": "system", "content": instructions}] + history
        debug_print(debug, "Getting chat completion for...:", messages)

        tools = [function_to_jsonschema(f) for f in agent.functions]
        # hide context_variables from model
        for tool in tools:
            params = tool["function"]["parameters"]
            params["properties"].pop(__CTX_VARS_NAME__, None)
            if __CTX_VARS_NAME__ in params.get("required", []):
                params["required"].remove(__CTX_VARS_NAME__)

        create_params = {
            "model": model_override or agent.model,
            "messages": messages,
            "response_format": response_format,
            "tools": tools or None,
            "tool_choice": agent.tool_choice,
            "stream": stream,
        }

        # Azure OpenAI API does not support `parallel_tool_calls` until 2024-08-01-preview.
        # See https://learn.microsoft.com/en-us/azure/ai-services/openai/api-version-deprecation#changes-between-2024-09-01-preview-and-2024-08-01-preview.
        #
        # if tools:
        #    create_params["parallel_tool_calls"] = agent.parallel_tool_calls

        # Azure OpenAI API does not support `refusal` and null `function_call`.
        for p in create_params["messages"]:
            fc = p.get("function_call", "")
            if fc is None:
                p.pop("function_call", None)
            p.pop("refusal", None)

            p.pop("reasoning_content", None)  # Remove possible reasoning content.

        try:
            response = await self.model.acompletion(**create_params)
            async for chunk in response:
                yield chunk
        except Exception as exc:
            # Return the error in form of a completion chunk.
            model = create_params["model"]
            chunk = ChatCompletionChunk(
                id="0",
                choices=[
                    Choice(
                        delta=ChoiceDelta(
                            role="assistant",
                            content=f"Failed to chat with {model}: {exc}",
                        ),
                        finish_reason="stop",
                        index=0,
                    )
                ],
                created="0",
                model=model,
                object="chat.completion.chunk",
            )
            yield chunk

    def handle_function_result(self, result, debug) -> Result:
        match result:
            case Result() as result:
                return result

            case Agent() as agent:
                return Result(
                    value=json.dumps({"assistant": agent.name}),
                    agent=agent,
                )
            case ChatMessage() as msg:
                return Result(
                    value=msg.content,
                    # add possible ctx vars
                    # context_variables={},
                )
            case _:
                try:
                    return Result(value=str(result))
                except Exception as e:
                    error_message = f"Failed to cast response to string: {result}. Make sure agent functions return a string or Result object. Error: {str(e)}"
                    debug_print(debug, error_message)
                    raise TypeError(error_message)

    async def handle_tool_calls(
        self,
        tool_calls: List[ChatCompletionMessageToolCall],
        functions: List[AgentFunction],
        context_variables: dict,
        debug: bool,
    ) -> AsyncIterator[Response | ChatMessage]:
        function_map = {f.__name__: f for f in functions}
        partial_response = Response(messages=[], agent=None, context_variables={})

        for tool_call in tool_calls:
            name = tool_call.function.name
            # handle missing tool case, skip to next tool
            if name not in function_map:
                debug_print(debug, f"Tool {name} not found in function map.")
                partial_response.messages.append(
                    {
                        # OpenAI seems to support only `role`, `tool_call_id` and `content`.
                        # See https://platform.openai.com/docs/guides/function-calling.
                        #
                        # Azure OpenAI supports one more parameter `name`.
                        # See https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/function-calling.
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": f"Error: Tool {name} not found.",
                    }
                )
                continue
            args = json.loads(tool_call.function.arguments or "{}")
            debug_print(debug, f"Processing tool call: {name} with arguments {args}")
            pretty_trace_tool_call(f"Initial Call: {name}", args)

            func = function_map[name]
            want_arg_names = get_func_args(func)
            args = {k: v for k, v in args.items() if k in want_arg_names}
            pretty_trace_tool_call(f"Actual Call: {name}", args)

            # pass context_variables to agent functions
            if __CTX_VARS_NAME__ in want_arg_names:
                args[__CTX_VARS_NAME__] = context_variables
            function_result = func(**args)

            if is_async_iterator(function_result):
                # NOTE(luopeng):
                #
                # The function is an async generator function. We assume that
                # it's better to return the stream directly to the user.
                #
                # Note that this only works if there's one tool call in the batch.
                async for chunk in function_result:
                    yield normalize_function_result(chunk)
                return

            function_result_after_await = await function_result
            if is_async_iterator(function_result_after_await):
                # NOTE(luopeng):
                #
                # The function returns an async iterator internally. We assume
                # that it's better to return the stream directly to the user.
                #
                # Note that this only works if there's one tool call in the batch.
                async for chunk in function_result_after_await:
                    yield normalize_function_result(chunk)
                return

            # Non-streaming results are handled here.
            raw_result = normalize_function_result(function_result_after_await)
            if raw_result.to_user:
                # Return the reply directly to the user.
                yield raw_result

            result: Result = self.handle_function_result(raw_result, debug)
            partial_response.messages.append(
                {
                    # OpenAI seems to support only `role`, `tool_call_id` and `content`.
                    # See https://platform.openai.com/docs/guides/function-calling.
                    #
                    # Azure OpenAI supports one more parameter `name`.
                    # See https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/function-calling.
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": result.value,
                }
            )
            partial_response.context_variables.update(result.context_variables)
            if result.agent:
                partial_response.agent = result.agent

        yield partial_response

    async def run_and_stream(
        self,
        agent: Agent,
        messages: List,
        response_format: dict | None = None,
        context_variables: dict = {},
        model_override: str = None,
        debug: bool = False,
        max_turns: int = float("inf"),
        execute_tools: bool = True,
    ) -> AsyncIterator[dict | ChatMessage]:
        active_agent = agent
        context_variables = copy.deepcopy(context_variables)
        history = copy.deepcopy(messages)
        init_len = len(messages)

        while len(history) - init_len < max_turns:
            message = {
                "content": "",
                "reasoning_content": "",
                # No `sender` param is supported by model
                # "sender": agent.name,
                "role": "assistant",
                "function_call": None,
                "tool_calls": defaultdict(
                    lambda: {
                        "function": {"arguments": "", "name": ""},
                        "id": "",
                        "type": "",
                    }
                ),
            }

            # get completion with current history, agent
            completion = self.get_chat_completion(
                agent=active_agent,
                history=history,
                response_format=response_format,
                context_variables=context_variables,
                model_override=model_override,
                stream=True,
                debug=debug,
            )

            yield {"delim": "start"}
            async for chunk in completion:
                delta = json.loads(chunk.choices[0].delta.json())
                if delta["role"] == "assistant":
                    delta["sender"] = active_agent.name

                delta_content = delta.get("content") or ""
                delta_reasoning_content = delta.get("reasoning_content") or ""
                if delta_content or delta_reasoning_content:
                    yield ChatMessage(
                        role=delta["role"] or "assistant",
                        content=delta_content,
                        reasoning_content=delta_reasoning_content,
                    )

                delta.pop("role", None)
                delta.pop("sender", None)
                merge_chunk(message, delta)
            yield {"delim": "end"}

            message["tool_calls"] = list(message.get("tool_calls", {}).values())
            if not message["tool_calls"]:
                message.pop("tool_calls", None)
            debug_print(debug, "Received completion:", message)
            history.append(message)

            if not message.get("tool_calls") or not execute_tools:
                debug_print(debug, "Ending turn.")
                break

            # convert tool_calls to objects
            tool_calls = []
            for tool_call in message["tool_calls"]:
                function = Function(
                    arguments=tool_call["function"]["arguments"],
                    name=tool_call["function"]["name"],
                )
                tool_call_object = ChatCompletionMessageToolCall(
                    id=tool_call["id"], function=function, type=tool_call["type"]
                )
                tool_calls.append(tool_call_object)

            # handle function calls, updating context_variables, and switching agents
            partial_response_or_iterator = self.handle_tool_calls(
                tool_calls, active_agent.functions, context_variables, debug
            )

            # partial_response is not a real stream response.
            is_real_stream_response = False
            async for chunk in partial_response_or_iterator:
                if isinstance(chunk, Response):
                    # If chunk is a Response object, update history and context_variables,
                    # and switch active_agent to try the next turn of the conversation.
                    partial_response = chunk

                    history.extend(partial_response.messages)
                    context_variables.update(partial_response.context_variables)
                    if partial_response.agent:
                        active_agent = partial_response.agent

                    # Just break the `async for` loop since there should only be one non-stream partial response.
                    break
                else:
                    is_real_stream_response = True
                    # If chunk is a normal ChatMessage, return it directly to the user.
                    yield chunk

            if is_real_stream_response:
                return

        yield {
            "response": Response(
                messages=history[init_len:],
                agent=active_agent,
                context_variables=context_variables,
            )
        }

    async def run(
        self,
        agent: Agent,
        messages: List,
        context_variables: dict = {},
        model_override: str = None,
        stream: bool = False,
        debug: bool = False,
        max_turns: int = float("inf"),
        execute_tools: bool = True,
    ) -> Response | AsyncIterator[dict[str, Any]]:
        if stream:
            return self.run_and_stream(
                agent=agent,
                messages=messages,
                context_variables=context_variables,
                model_override=model_override,
                debug=debug,
                max_turns=max_turns,
                execute_tools=execute_tools,
            )
        active_agent = agent
        context_variables = copy.deepcopy(context_variables)
        history = copy.deepcopy(messages)
        init_len = len(messages)

        while len(history) - init_len < max_turns and active_agent:
            # get completion with current history, agent
            completion = await self.get_chat_completion(
                agent=active_agent,
                history=history,
                context_variables=context_variables,
                model_override=model_override,
                stream=stream,
                debug=debug,
            )
            message = completion.choices[0].message
            debug_print(debug, "Received completion:", message)
            # No `sender` param is supported by model
            # message.sender = active_agent.name
            msg = json.loads(message.model_dump_json())
            # Azure OpenAI API does not support empty `tool_calls` and `audio`.
            tc = msg.get("tool_calls")
            if not tc:
                msg.pop("tool_calls", None)
            msg.pop("audio", None)
            history.append(msg)  # to avoid OpenAI types (?)

            if not message.tool_calls or not execute_tools:
                debug_print(debug, "Ending turn.")
                break

            # handle function calls, updating context_variables, and switching agents
            partial_response = await self.handle_tool_calls(
                message.tool_calls, active_agent.functions, context_variables, debug
            )
            history.extend(partial_response.messages)
            context_variables.update(partial_response.context_variables)
            if partial_response.agent:
                active_agent = partial_response.agent

        return Response(
            messages=history[init_len:],
            agent=active_agent,
            context_variables=context_variables,
        )
