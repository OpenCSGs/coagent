from typing import AsyncIterator, Callable, Type

from coagent.core import Context, GenericMessage, handler, Message
from jinja2 import Template
from pydantic import BaseModel

from .chat_agent import ChatAgent
from .messages import ChatHistory, ChatMessage, type_to_response_format_param
from .model import default_model, Model


class StructuredAgent(ChatAgent):
    def __init__(
        self,
        input_type: Type[Message],
        output_type: Type[BaseModel] | Type[str] = str,
        system: str = "",
        messages: list[ChatMessage] | None = None,
        tools: list[Callable] | None = None,
        model: Model = default_model,
    ):
        super().__init__(system=system, tools=tools, model=model)
        self._input_type: Type[Message] = input_type
        self._output_type: Type[BaseModel] | Type[str] = output_type

        self.__messages: list[ChatMessage] | None = messages

    async def render_system(self, _input: Message) -> str:
        """Render the system prompt.

        This is a default implementation that renders the system prompt using Jinja2.
        Override this method to implement custom rendering logic.
        """
        if not self._system:
            return ""
        return Template(self._system).render(_input.model_dump())

    async def render_messages(self, _input: Message) -> list[ChatMessage]:
        """Render the chat messages.

        This is a default implementation that renders the chat messages using Jinja2.
        Override this method to implement custom rendering logic.
        """
        if self.__messages:
            data = _input.model_dump()
            return [
                ChatMessage(role=m.role, content=Template(m.content).render(data))
                for m in self.__messages
            ]

        # No initial messages are provided.
        # Build the chat messages based on the input message.
        match _input:
            case ChatMessage():
                return [_input]
            case ChatHistory():
                return _input.messages
            case _:
                return [ChatMessage(role="user", content=_input.model_dump_json())]

    @handler
    async def handle(
        self, msg: GenericMessage, ctx: Context
    ) -> AsyncIterator[ChatMessage]:
        _input = self._input_type.decode(msg.raw)

        # This is a hack to make the system prompt dynamic.
        swarm_agent = await self.get_swarm_agent()
        swarm_agent.instructions = await self.render_system(_input)

        messages = await self.render_messages(_input)

        history = ChatHistory(messages=messages)
        output_schema: dict | None = None
        if self._output_type is not str:
            output_schema = type_to_response_format_param(self._output_type)

        response = self._handle_history(history, output_schema)
        async for resp in response:
            yield resp
