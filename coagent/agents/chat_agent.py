from __future__ import annotations

import functools
import inspect
import re
from typing import Any, AsyncIterator, Callable

from coagent.core import Address, BaseAgent, Context, handler, logger
from pydantic.fields import FieldInfo

from .aswarm import Agent as SwarmAgent, Swarm
from .messages import ChatMessage, ChatHistory
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


def confirm(template: str):
    """Decorator to ask the user to confirm, if not yet, by sending a message
    which will be constructed from the given template.
    """

    def wrapper(func):
        @functools.wraps(func)
        async def run(*args: Any, **kwargs: Any) -> ChatMessage | str:
            # Ask the user to confirm if not yet.
            ctx = kwargs.get("ctx", None)
            if ctx and not RunContext(ctx).user_confirmed:
                # We assume that all meaningful arguments (includes `ctx` but
                # excepts possible `self`) are keyword arguments. Therefore,
                # here we use kwargs as the source of template variables.
                tmpl_vars = {
                    k: v.default if isinstance(v, FieldInfo) else v
                    for k, v in kwargs.items()
                }
                return ChatMessage(
                    role="assistant",
                    content=template.format(**tmpl_vars),
                    type="confirm",
                    to_user=True,
                )

            # Note that we assume that the tool is not an async generator,
            # so we always use `await` here.
            return await func(*args, **kwargs)

        return run

    return wrapper


class Delegate:
    """A delegate agent that helps to handle a specific task."""

    def __init__(self, host_agent: ChatAgent, agent_type: str):
        self.host_agent: ChatAgent = host_agent
        self.agent_type: str = agent_type

    async def handle(self, msg: ChatHistory) -> AsyncIterator[ChatMessage]:
        addr = Address(name=self.agent_type, id=self.host_agent.address.id)
        result = self.host_agent.channel.publish_multi(addr, msg.encode())
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
    async def run(*args: Any, **kwargs: Any) -> ChatMessage | str:
        try:
            # Note that we assume that the tool is not an async generator,
            # so we always use `await` here.
            return await func(*args, **kwargs)
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

        self._name = name
        self._system = system
        self._client = client

        tools = tools or []
        methods = inspect.getmembers(self, predicate=inspect.ismethod)
        for name, meth in methods:
            if getattr(meth, "is_tool", False):
                tools.append(meth)

        self._swarm_client = Swarm(self.client.azure_client)

        self._swarm_agent = SwarmAgent(
            name=self.name,
            model=self.client.model,
            instructions=self.system,
            functions=[wrap_error(t) for t in tools],
        )

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
    def client(self) -> ModelClient:
        return self._client

    async def agent(self, agent_type: str) -> AsyncIterator[ChatMessage]:
        """The candidate agent to delegate the conversation to."""
        async for chunk in Delegate(self, agent_type).handle(self._history):
            yield chunk

    @handler
    async def handle(
        self, msg: ChatHistory, ctx: Context
    ) -> AsyncIterator[ChatMessage]:
        # For now, we assume that the agent is processing messages sequentially.
        self._history: ChatHistory = msg

        await self.update_user_confirmed(self._history)

        response = self._swarm_client.run_and_stream(
            agent=self._swarm_agent,
            messages=[m.model_dump() for m in msg.messages],
            context_variables=msg.extensions,
        )
        async for resp in response:
            if isinstance(resp, ChatMessage) and resp.content:
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