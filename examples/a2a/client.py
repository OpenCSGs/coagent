import argparse
import asyncio
from typing import Any
from uuid import uuid4

from a2a.client import A2AClient
from a2a.types import (
    MessageSendParams,
    SendMessageRequest,
    SendStreamingMessageRequest,
)
import httpx


async def main(url: str):
    """
    References:
    - https://a2aproject.github.io/A2A/v0.2.5/tutorials/python/6-interact-with-server/
    - https://github.com/a2aproject/a2a-samples/blob/main/samples/python/agents/helloworld/test_client.py
    """

    async with httpx.AsyncClient() as httpx_client:
        client = A2AClient(httpx_client=httpx_client, url=url)
        send_message_payload: dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "你好"}],
                "messageId": uuid4().hex,
                "taskId": uuid4().hex,
            },
        }

        # Non-streaming request
        request = SendMessageRequest(
            id=str(uuid4()), params=MessageSendParams(**send_message_payload)
        )
        response = await client.send_message(request)

        print("Non-streaming response:")
        print(response.model_dump(mode="json", exclude_none=True))

        # Streaming request
        streaming_request = SendStreamingMessageRequest(
            id=str(uuid4()), params=MessageSendParams(**send_message_payload)
        )
        stream_response = client.send_message_streaming(streaming_request)

        print("Streaming response:")
        async for chunk in stream_response:
            print(chunk.model_dump(mode="json", exclude_none=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="The agent URL")
    args = parser.parse_args()

    asyncio.run(main(url=args.url))
