from typing import Any, AsyncIterator
import uuid

try:
    from a2a.client import A2AClient
    from a2a.types import (
        AgentCard,
        JSONRPCErrorResponse,
        Message,
        MessageSendParams,
        SendMessageRequest,
        SendMessageResponse,
        SendMessageSuccessResponse,
        SendStreamingMessageRequest,
        SendStreamingMessageResponse,
        SendStreamingMessageSuccessResponse,
    )
except ImportError as exc:
    raise ImportError(
        "A2A package requires a2a-sdk. "
        "Install with 'pip install coagent-python[a2a]'"
    ) from exc

from coagent.agents import ChatAgent, ChatHistory, ChatMessage
from coagent.core.exceptions import InternalError
import httpx


class A2AAgent(ChatAgent):
    """A proxy agent that delegate messages to an A2A agent."""

    def __init__(self, httpx_client: httpx.AsyncClient, card: AgentCard):
        super().__init__()

        self.card = card
        self.a2a_client = A2AClient(httpx_client=httpx_client, agent_card=self.card)

    async def _handle_history(
        self,
        msg: ChatHistory,
        response_format: dict | None = None,
    ) -> AsyncIterator[ChatMessage]:
        # For now, we can only send a single message, since A2A does not support send chat history:
        # https://github.com/a2aproject/A2A/issues/59
        # https://github.com/a2aproject/A2A/issues/274

        # TODO: Need to explore how to pass history.extensions as RunContext in A2A

        message_payload: dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": msg.messages[-1].content}],
                "messageId": uuid.uuid4().hex,
                "taskId": uuid.uuid4().hex,
            },
        }

        # Non-streaming
        if not self.card.capabilities.streaming:
            request = SendMessageRequest(
                id=str(uuid.uuid4()), params=MessageSendParams(**message_payload)
            )
            response = await self.a2a_client.send_message(request)
            yield a2a_response_to_chat_message(response)
        else:
            # Streaming
            request = SendStreamingMessageRequest(
                id=str(uuid.uuid4()), params=MessageSendParams(**message_payload)
            )
            response = self.a2a_client.send_message_streaming(request)
            async for chunk in response:
                yield a2a_response_to_chat_message(chunk)


def a2a_response_to_chat_message(
    resp: SendMessageResponse | SendStreamingMessageResponse,
) -> ChatMessage:
    match resp.root:
        case JSONRPCErrorResponse():
            raise InternalError(resp.root.error.model_dump_json(exclude_none=True))

        case SendMessageSuccessResponse():
            result = resp.root.result
            match result:
                case Message():
                    content = result.parts[0].root.text
                    return ChatMessage(role="assistant", content=content)

        case SendStreamingMessageSuccessResponse():
            result = resp.root.result
            match result:
                case Message():
                    content = result.parts[0].root.text
                    return ChatMessage(role="assistant", content=content)

    raise InternalError(
        f"Unsupported A2A response: {resp.model_dump_json(exclude_none=True)}"
    )
