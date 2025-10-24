import asyncio
from collections import defaultdict
import inspect
import json
import re
from typing import Any, AsyncIterator, Callable
import time

from coagent.core import (
    BaseAgent,
    Context,
    handler,
)
from coagent.core.util import get_func_args, pretty_trace_tool_call
from openai.types.responses import (
    EasyInputMessageParam,
    ResponseOutputText,
    ResponseFunctionToolCallParam,
    ResponseFunctionToolCallOutputItem,
)
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import Choice, ChoiceDelta

from .model_settings import ModelSettings
from .util import (
    function_to_jsonschema,
    __CTX_VARS_NAME__,
)
from .context import TData, RunContext
from .types import (
    TResponseInputItem,
    ResponseFunctionToolCall,
    ToolCallItem,
    ToolCallOutputItem,
    ResponseOutputMessage,
    MessageOutputItem,
    StreamEvent,
)
from .messages import InputHistory, OutputMessage
from ..model import default_model, Model
from .converter import Converter

FAKE_ID = "__fake_id__"


class ReActAgent(BaseAgent):
    """An autonomous agent that handles tasks using an agent loop.

    Args:
        system: The system instruction for the agent.
        tools: A list of tools that the agent can use.
        model: The model to use for generating responses.
        timeout: The timeout for the agent.
    """

    def __init__(
        self,
        name: str,
        system: str = "",
        tools: list[Callable] | None = None,
        model: Model = default_model,
        model_settings: ModelSettings | None = None,
        timeout: float = 300,
    ):
        super().__init__(timeout=timeout)

        self._name: str = name
        self._system: str = system
        self._tools: list[Callable] = tools or []
        self._model: Model = model
        self._model_settings: ModelSettings = model_settings or ModelSettings()

    @property
    def name(self) -> str:
        if self._name:
            return self._name

        n = self.__class__.__name__
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", n).lower()

    @property
    def system(self) -> str:
        """The system instruction for this agent."""
        return self._system

    @property
    def tools(self) -> list[Callable]:
        return self._tools

    @property
    def model(self) -> Model:
        return self._model

    @property
    def model_settings(self) -> ModelSettings:
        return self._model_settings

    @handler
    async def handle_history(
        self, msg: InputHistory, ctx: Context
    ) -> AsyncIterator[OutputMessage]:
        input: list[TResponseInputItem] = [
            EasyInputMessageParam(role=m.role, content=m.content) for m in msg.messages
        ]
        data = msg.extensions

        loop = AgentLoop(self)
        result = loop.run(input=input, data=data)

        try:
            async for item in result.stream_events():
                yield OutputMessage(item=item)  # type: ignore
        except asyncio.CancelledError:
            result.cancel()  # Clean up resources.
            raise


DEFAULT_MAX_TURNS = 10


class QueueCompleteSentinel:
    pass


class StreamResult:
    def __init__(self, queue: asyncio.Queue, run_task: asyncio.Task):
        self._queue: asyncio.Queue = queue
        self._run_task: asyncio.Task = run_task
        self._cancel_event: asyncio.Event = asyncio.Event()

    def cancel(self) -> None:
        """Cancel the streaming run, stopping all background tasks."""
        # Cancel the running task and the stream_events() loop.
        self._run_task.cancel()
        self._cancel_event.set()

        # Clear the queue to prevent processing stale events.
        while not self._queue.empty():
            self._queue.get_nowait()

    async def stream_events(self) -> AsyncIterator[StreamEvent]:
        """Stream deltas for new events as they are generated."""
        while True:
            if self._cancel_event.is_set():
                break

            item = await self._queue.get()
            self._queue.task_done()

            if isinstance(item, QueueCompleteSentinel):
                break

            yield item


class AgentLoop:
    def __init__(self, agent: ReActAgent):
        self.agent: ReActAgent = agent
        self._queue: asyncio.Queue[StreamEvent | QueueCompleteSentinel] = (
            asyncio.Queue()
        )

    def run(
        self,
        input: list[TResponseInputItem],
        max_turns: int = DEFAULT_MAX_TURNS,
        data: TData | None = None,
    ) -> StreamResult:
        ctx: RunContext = RunContext(_data=data, _queue=self._queue)
        run_task: asyncio.Task = asyncio.create_task(self._run(ctx, input, max_turns))
        return StreamResult(self._queue, run_task)

    async def _run(
        self,
        ctx: RunContext,
        input: list[TResponseInputItem],
        max_turns: int,
    ) -> None:
        current_turn = 0
        history: list[TResponseInputItem] = input.copy()

        while True:
            current_turn += 1
            if current_turn > max_turns:
                # raise MaxTurnsExceeded(f"Max turns ({max_turns}) exceeded")
                raise RuntimeError(f"Max turns ({max_turns}) exceeded")

            has_tool_call: bool = False
            response: AsyncIterator[ChatCompletionChunk] = self.get_chat_completion(
                history, {}, True
            )
            async for item in self.handle_stream(response):
                if isinstance(item, ToolCallItem):
                    has_tool_call = True

                    self._queue.put_nowait(item)
                    history.append(
                        # ResponseFunctionToolCall => ResponseFunctionToolCallParam
                        ResponseFunctionToolCallParam(**item.raw_item.model_dump())
                    )

                    output = await self.handle_function_call(ctx, item.raw_item)
                    if output:
                        self._queue.put_nowait(output)
                        history.append(output.raw_item)

                elif isinstance(item, MessageOutputItem):
                    self._queue.put_nowait(item)

            # The response does not include any tool calls, so we can break out of the loop.
            if not has_tool_call:
                break

        # Signal that the stream is complete.
        self._queue.put_nowait(QueueCompleteSentinel())

    async def handle_stream(
        self, response: AsyncIterator[ChatCompletionChunk]
    ) -> AsyncIterator[StreamEvent]:
        function_calls: dict[int, ResponseFunctionToolCall] = {}

        async for chunk in response:
            if not chunk.choices or not chunk.choices[0].delta:
                continue

            delta = chunk.choices[0].delta

            # Handle regular content
            if delta.content:
                # Start a new assistant message stream
                yield MessageOutputItem(
                    type="message_output_item",
                    raw_item=ResponseOutputMessage(
                        id=FAKE_ID,
                        content=[
                            ResponseOutputText(
                                text=delta.content,
                                type="output_text",
                                annotations=[],
                            ),
                        ],
                        role="assistant",
                        type="message",
                        status="in_progress",
                    ),
                )

            # Handle tool calls
            tool_calls = delta.tool_calls or []
            if tool_calls:
                for tc_delta in tool_calls:
                    if tc_delta.index not in function_calls:
                        function_calls[tc_delta.index] = ResponseFunctionToolCall(
                            id=FAKE_ID,
                            arguments="",
                            name="",
                            type="function_call",
                            call_id="",
                        )

                    tc_function = tc_delta.function

                    # Accumulate arguments as they come in
                    function_calls[tc_delta.index].arguments += (
                        tc_function.arguments if tc_function else ""
                    ) or ""

                    # Set function name directly (it's correct from the first function call chunk)
                    if tc_function and tc_function.name:
                        function_calls[tc_delta.index].name = tc_function.name

                    if tc_delta.id:
                        function_calls[tc_delta.index].call_id = tc_delta.id

        # Send completion events for function calls
        for _, function_call in function_calls.items():
            yield ToolCallItem(
                type="tool_call_item",
                raw_item=function_call,
            )

    async def handle_function_call(
        self,
        ctx: RunContext,
        function_call: ResponseFunctionToolCall,
    ) -> ToolCallOutputItem | None:
        function_map = {f.__name__: f for f in self.agent.tools}
        name = function_call.name

        # handle missing tool case, skip to next tool
        if name not in function_map:
            """
            {
                # OpenAI seems to support only `role`, `tool_call_id` and `content`.
                # See https://platform.openai.com/docs/guides/function-calling.
                #
                # Azure OpenAI supports one more parameter `name`.
                # See https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/function-calling.
                "role": "tool",
                "tool_call_id": function_call.id,
                "name": name,
                "content": f"Error: Tool {name} not found.",
            }
            """
            return

        args = json.loads(function_call.arguments or "{}")
        pretty_trace_tool_call(f"Initial Call: {name}", args)

        func = function_map[name]
        want_arg_names = get_func_args(func)
        args = {k: v for k, v in args.items() if k in want_arg_names}
        pretty_trace_tool_call(f"Actual Call: {name}", args)

        # TODO: Check by argument types instead of names. E.g. `ctx` could be a `RunContext`.
        if __CTX_VARS_NAME__ in want_arg_names:
            args[__CTX_VARS_NAME__] = RunContext.with_tool(
                ctx,
                name=function_call.name,
                call_id=function_call.call_id,
                arguments=function_call.arguments,
            )

        raw_result = func(**args)
        if inspect.isawaitable(raw_result):
            result = await raw_result
        else:
            result = raw_result

        return ToolCallOutputItem(
            raw_item=ResponseFunctionToolCallOutputItem(
                id="",
                call_id=function_call.call_id,
                output=str(result),
                type="function_call_output",
                status="completed",
            ),
            output=result,
            type="tool_call_output_item",
        )

    async def get_chat_completion(
        self,
        history: list[TResponseInputItem],
        context_variables: dict[str, Any],
        stream: bool,
        response_format: dict | None = None,
    ) -> AsyncIterator[ChatCompletionChunk]:
        context_variables = defaultdict(str, context_variables)
        messages = Converter.items_to_messages(history)

        if self.agent.system:
            messages.insert(
                0,
                {
                    "content": self.agent.system,
                    "role": "system",
                },
            )

        tools = [function_to_jsonschema(tool) for tool in self.agent.tools]
        # hide context_variables from model
        for tool in tools:
            params = tool["function"]["parameters"]
            params["properties"].pop(__CTX_VARS_NAME__, None)
            if __CTX_VARS_NAME__ in params.get("required", []):
                params["required"].remove(__CTX_VARS_NAME__)

        create_params = {
            "messages": messages,
            "response_format": response_format,
            "tools": tools or None,
            "tool_choice": self.agent.model_settings.tool_choice,
            "stream": stream,
        }

        # Azure OpenAI API does not support `refusal` and null `function_call`.
        for p in create_params["messages"]:
            fc = p.get("function_call", "")
            if fc is None:
                p.pop("function_call", None)
            p.pop("refusal", None)

            p.pop("reasoning_content", None)  # Remove possible reasoning content.

        try:
            response = await self.agent.model.acompletion(**create_params)
            async for chunk in response:  # type: ignore
                yield chunk
        except Exception as exc:
            # Return the error in form of a completion chunk.
            model = self.agent.model.id
            chunk = ChatCompletionChunk(
                id=FAKE_ID,
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
                created=int(time.time()),
                model=model,
                object="chat.completion.chunk",
            )
            yield chunk
