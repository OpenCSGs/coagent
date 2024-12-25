"""Most of the Textual code is borrowed from https://gist.github.com/willmcgugan/648a537c9d47dafa59cb8ece281d8c2c."""

import argparse
import json
from typing import List, Union, AsyncIterator
import uuid

from coagent.agents.chat_agent import ChatHistory, ChatMessage
from coagent.core import Address, set_stderr_logger
from coagent.runtimes import NATSRuntime, HTTPRuntime

from textual import on, work
from textual.app import App, ComposeResult
from textual.widgets import Header, Input, Footer, Markdown, Button
from textual.containers import Horizontal, VerticalScroll


class Bot:
    runtime: NATSRuntime | None = None
    history: ChatHistory = ChatHistory(messages=[])
    addr: Address | None = None
    server: Union[str, List[str], None] = None
    auth: str = ""
    ext: dict | None = None

    @classmethod
    async def ainit(cls):
        if cls.server.startswith("nats://"):
            runtime = NATSRuntime.from_servers(cls.server)
        elif cls.server.startswith(("http://", "https://")):
            runtime = HTTPRuntime.from_server(cls.server, cls.auth)
        else:
            raise ValueError(f"Unsupported server: {cls.server}")
        cls.runtime = runtime
        await cls.runtime.start()

        cls.history.extensions = cls.ext or {}

    @classmethod
    async def asend(cls, query: str) -> AsyncIterator[ChatMessage]:
        msg = ChatMessage(role="user", content=query)
        cls.history.messages.append(msg)
        result = cls.runtime.channel.publish_multi(
            cls.addr,
            cls.history.encode(),
        )
        full_reply = ChatMessage(role="assistant", content="")
        async for chunk in result:
            reply = ChatMessage.decode(chunk)

            full_reply.to_user = reply.to_user
            full_reply.type = reply.type
            full_reply.content += reply.content

            yield reply
        cls.history.messages.append(full_reply)

    @classmethod
    async def clear(cls):
        cls.history.messages.clear()


class Prompt(Markdown):
    pass


class Response(Markdown):
    BORDER_TITLE = "Assistant"


class BotApp(App):
    AUTO_FOCUS = "Input"

    CSS = """
    Prompt {
        background: $primary 10%;
        color: $text;
        margin: 1;
        margin-right: 8;
        padding: 1 2 0 2;
    }

    Response {
        border: wide $success;
        background: $success 10%;
        color: $text;
        margin: 1;
        margin-left: 8;
        padding: 1 2 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="chat-view"):
            yield Response("Good day! How can I assist you?")
        yield Input(placeholder="Input")
        # with Horizontal():
        #     yield Input(placeholder="Input")
        #     yield Button("Clear", id="clear-button")
        yield Footer()

    async def on_mount(self) -> None:
        await Bot.ainit()

    @on(Button.Pressed, "#clear-button")
    async def on_clear(self, event: Button.Pressed) -> None:
        await Bot.clear()

    @on(Input.Submitted)
    async def on_input(self, event: Input.Submitted) -> None:
        chat_view = self.query_one("#chat-view")
        event.input.clear()
        await chat_view.mount(Prompt(event.value))
        chat_view.scroll_end()

        await chat_view.mount(response := Response())
        await self.send_prompt(event.value, response)
        chat_view.scroll_end()

    async def send_prompt(self, prompt: str, response: Response) -> None:
        bot_response = Bot.asend(prompt)
        full_content = ""
        async for chunk in bot_response:
            if not full_content and chunk.sender:
                full_content = f"[{chunk.sender}] "
            full_content += chunk.content
            await response.update(full_content)


if __name__ == "__main__":
    set_stderr_logger("ERROR")

    parser = argparse.ArgumentParser()
    parser.add_argument("agent", type=str)
    parser.add_argument("--server", type=str, default="nats://localhost:4222")
    parser.add_argument("--auth", type=str, default="")
    parser.add_argument("--ext", type=str, default="{}")
    args = parser.parse_args()

    session_id = uuid.uuid4().hex
    Bot.addr = Address(name=args.agent, id=session_id)
    Bot.server = args.server
    Bot.auth = args.auth
    Bot.ext = json.loads(args.ext)

    app = BotApp()
    app.run()
