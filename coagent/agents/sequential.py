from coagent.core import (
    Address,
    BaseAgent,
    Context,
    GenericMessage,
    NO_REPLY,
    Reply,
    SetReplyInfo,
    handler,
)


class Sequential(BaseAgent):
    """Sequential is a composite agent that orchestrates its children sequentially."""

    def __init__(self, *agent_types: str):
        super().__init__()
        self._agent_types = agent_types

    async def started(self) -> None:
        for i in range(len(self._agent_types) - 1):
            # Set the reply address of the current agent to be the next agent.
            addr = Address(name=self._agent_types[i], id=self.address.id)
            next_addr = Address(name=self._agent_types[i + 1], id=self.address.id)
            reply = Reply(address=next_addr)
            await self.channel.publish(
                addr,
                SetReplyInfo(reply_info=reply).encode(),
            )

        # Set the current agent to no-reply mode.
        await self._set_reply_info(NO_REPLY)

    @handler
    async def handle(self, msg: GenericMessage, ctx: Context) -> None:
        if len(self._agent_types) == 0:
            raise RuntimeError("No agent types provided.")

        # Let the last agent reply to the sending agent, if asked.
        reply = msg.reply
        if reply:
            last_addr = Address(name=self._agent_types[-1], id=self.address.id)
            await self.channel.publish(
                last_addr,
                SetReplyInfo(reply_info=reply).encode(),
            )

        # Send the message to the first agent in the list.
        addr = Address(name=self._agent_types[0], id=self.address.id)
        await self.channel.publish(addr, msg.encode())
