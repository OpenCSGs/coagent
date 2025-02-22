from __future__ import annotations

import functools
import inspect
import json
import re
from typing import Any, AsyncIterator, Callable

from coagent.core import Address, BaseAgent, Context, handler, logger
from coagent.core.agent import is_async_iterator
from pydantic_core import PydanticUndefined
from pydantic.fields import FieldInfo

from .aswarm import Agent as SwarmAgent, Swarm
from .aswarm.util import function_to_jsonschema
from .messages import ChatMessage, ChatHistory, StructuredOutput
from .model_client import default_model_client, ModelClient
from .util import is_user_confirmed


class RunContext(dict):
    """RunContext holds a dictionary of context variables that are available to all tools of a running agent."""

    @property
    def user_confirmed(self) -> bool:
        return self.get("user_confirmed", False)

    @user_confirmed.setter
    def user_confirmed(self, value: bool) -> None:
        self["user_confirmed"] = value

    @property
    def user_submitted(self) -> bool:
        return self.get("user_submitted", False)

    @user_submitted.setter
    def user_submitted(self, value: bool) -> None:
        self["user_submitted"] = value


def confirm(template: str):
    """Decorator to ask the user to confirm, if not yet, by sending a message
    which will be constructed from the given template.
    """

    def wrapper(func):
        @functools.wraps(func)
        async def run(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[ChatMessage | str] | ChatMessage | str:
            # Ask the user to confirm if not yet.
            ctx = kwargs.get("ctx", None)
            if ctx and not RunContext(ctx).user_confirmed:
                # We assume that all meaningful arguments (includes `ctx` but
                # excepts possible `self`) are keyword arguments. Therefore,
                # here we use kwargs directly as the template variables.
                return ChatMessage(
                    role="assistant",
                    content=template.format(**kwargs),
                    type="confirm",
                    to_user=True,
                )

            result = func(*args, **kwargs)
            if is_async_iterator(result):
                return result
            else:
                return await result

        return run

    return wrapper


def submit(template: str = ""):
    """Decorator to ask the user to fill in the input form, if not yet, by
    sending a message which holds the input schema of the current tool.
    """
    template = (
        template
        or """\
Please fill in the input form below:

```schema
{schema}
```

```input
{input}
```\
"""
    )

    def wrapper(func):
        @functools.wraps(func)
        async def run(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[ChatMessage | str] | ChatMessage | str:
            # Ask the user to fill in the input form if not yet.
            ctx = kwargs.get("ctx", None)
            if ctx and not RunContext(ctx).user_submitted:
                raw = function_to_jsonschema(func)
                schema_json = json.dumps(raw["function"], ensure_ascii=False, indent=2)
                # We assume that all meaningful arguments (includes `ctx` but
                # excepts possible `self`) are keyword arguments. Therefore,
                # here we use kwargs directly as the template variables.
                input_ = {k: v for k, v in kwargs.items() if k != "ctx"}
                input_json = json.dumps(input_, ensure_ascii=False, indent=2)

                return ChatMessage(
                    role="assistant",
                    content=template.format(schema=schema_json, input=input_json),
                    type="submit",
                    to_user=True,
                )

            result = func(*args, **kwargs)
            if is_async_iterator(result):
                return result
            else:
                return await result

        return run

    return wrapper


class Delegate:
    """A delegate agent that helps to handle a specific task."""

    def __init__(self, host_agent: ChatAgent, agent_type: str):
        self.host_agent: ChatAgent = host_agent
        self.agent_type: str = agent_type

    async def handle(self, msg: ChatHistory) -> AsyncIterator[ChatMessage]:
        addr = Address(name=self.agent_type, id=self.host_agent.address.id)
        result = await self.host_agent.channel.publish(addr, msg.encode(), stream=True)
        full_content = ""
        async for chunk in result:
            resp = ChatMessage.decode(chunk)
            if not resp.sender:
                # Set the sender to the current agent if not specified.
                resp.sender = self.agent_type
            yield resp
            full_content += resp.content
        # FIXME: no need to save message if user always provide the complete chat history.
        # msg.messages.append(ChatMessage(role="assistant", content=full_content))


def tool(func):
    """Decorator to mark the given function as a Coagent tool."""
    func.is_tool = True
    return func


def wrap_error(func):
    """Decorator to capture and return the possible error when running the given tool."""

    @functools.wraps(func)
    async def run(
        *args: Any, **kwargs: Any
    ) -> AsyncIterator[ChatMessage | str] | ChatMessage | str:
        try:
            # Fill in the missing arguments with default values if possible.
            #
            # Note that we assume that all meaningful arguments (includes `ctx`
            # but excepts possible `self`) are keyword arguments.
            sig = inspect.signature(func)
            for name, param in sig.parameters.items():
                if name not in kwargs and isinstance(param.default, FieldInfo):
                    default = param.default.default
                    if default is PydanticUndefined:
                        raise ValueError(f"Missing required argument {name!r}")
                    else:
                        kwargs[name] = default

            result = func(*args, **kwargs)
            if is_async_iterator(result):
                return result
            else:
                return await result

        except Exception as exc:
            logger.exception(exc)
            return f"Error: {exc}"

    return run


class ChatAgent(BaseAgent):
    def __init__(
        self,
        name: str = "",
        system: str = "",
        tools: list[Callable] | None = None,
        client: ModelClient = default_model_client,
    ):
        super().__init__()

        self._name: str = name
        self._system: str = system
        self._tools: list[Callable] = tools or []
        self._client: ModelClient = client

        self._swarm_client: Swarm = Swarm(self.client)
        self._swarm_agent: SwarmAgent | None = None

        self._history: ChatHistory = ChatHistory(messages=[])

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
    def client(self) -> ModelClient:
        return self._client

    async def get_swarm_agent(self) -> SwarmAgent:
        if not self._swarm_agent:
            tools = self.tools[:]  # copy
            methods = inspect.getmembers(self, predicate=inspect.ismethod)
            for _name, meth in methods:
                if getattr(meth, "is_tool", False):
                    tools.append(meth)

            self._swarm_agent = SwarmAgent(
                name=self.name,
                model=self.client.model,
                instructions=self.system,
                functions=[wrap_error(t) for t in tools],
            )
        return self._swarm_agent

    async def agent(self, agent_type: str) -> AsyncIterator[ChatMessage]:
        """The candidate agent to delegate the conversation to."""
        async for chunk in Delegate(self, agent_type).handle(self._history):
            yield chunk

    @handler
    async def handle_history(
        self, msg: ChatHistory, ctx: Context
    ) -> AsyncIterator[ChatMessage]:
        response = self._handle_history(msg)
        async for resp in response:
            yield resp

    @handler
    async def handle_message(
        self, msg: ChatMessage, ctx: Context
    ) -> AsyncIterator[ChatMessage]:
        history = ChatHistory(messages=[msg])
        response = self._handle_history(history)
        async for resp in response:
            yield resp

    @handler
    async def handle_structured_output(
        self, msg: StructuredOutput, ctx: Context
    ) -> AsyncIterator[ChatMessage]:
        match msg.input:
            case ChatMessage():
                history = ChatHistory(messages=[msg.input])
                response = self._handle_history(history, msg.output_schema)
                async for resp in response:
                    yield resp
            case ChatHistory():
                response = self._handle_history(msg.input, msg.output_schema)
                async for resp in response:
                    yield resp

    async def _handle_history(
        self,
        msg: ChatHistory,
        response_format: dict | None = None,
    ) -> AsyncIterator[ChatMessage]:
        # For now, we assume that the agent is processing messages sequentially.
        self._history: ChatHistory = msg

        await self.update_user_confirmed(msg)
        await self.update_user_submitted(msg)

        swarm_agent = await self.get_swarm_agent()

        response = self._swarm_client.run_and_stream(
            agent=swarm_agent,
            messages=[m.model_dump() for m in msg.messages],
            response_format=response_format,
            context_variables=msg.extensions,
        )
        async for resp in response:
            if isinstance(resp, ChatMessage) and resp.has_content:
                yield resp

    async def update_user_confirmed(self, history: ChatHistory) -> None:
        ctx = RunContext(history.extensions)
        user_confirmed = ctx.user_confirmed
        is_reply_to_confirm_message = await self._has_confirm_message(history)

        if user_confirmed:
            if not is_reply_to_confirm_message:
                user_confirmed = False
        else:
            if is_reply_to_confirm_message:
                user_confirmed = await is_user_confirmed(
                    history.messages[-1].content, self.client
                )

        ctx.user_confirmed = user_confirmed
        history.extensions = ctx

    async def _has_confirm_message(self, history: ChatHistory) -> bool:
        """Check if the penultimate message is a confirmation message."""
        return len(history.messages) > 1 and history.messages[-2].type == "confirm"

    async def update_user_submitted(self, history: ChatHistory) -> None:
        ctx = RunContext(history.extensions)
        ctx.user_submitted = await self._is_submit_message(history)
        history.extensions = ctx

    async def _is_submit_message(self, history: ChatHistory) -> bool:
        """Check if the last message is a user submission message."""
        if len(history.messages) == 0:
            return False
        last_msg = history.messages[-1]
        return last_msg.role == "user" and last_msg.type == "submit"
