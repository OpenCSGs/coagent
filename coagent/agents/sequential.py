from coagent.core import (
    Address,
    BaseAgent,
    Context,
    GenericMessage,
    Reply,
    SetReplyAgent,
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
                SetReplyAgent(reply_info=reply).encode(),
            )

    @handler
    async def handle(self, msg: GenericMessage, ctx: Context) -> None:
        if len(self._agent_types) == 0:
            return

        # Let the last agent reply to the sending agent, if asked.
        reply = self.reply or msg.reply
        if reply:
            last_addr = Address(name=self._agent_types[-1], id=self.address.id)
            await self.channel.publish(
                last_addr,
                SetReplyAgent(reply_info=reply).encode(),
            )
            # Reset the reply address of the message, since it will be replied by the last agent.
            msg.reply = None

        # Send the message to the first agent in the list.
        addr = Address(name=self._agent_types[0], id=self.address.id)
        await self.channel.publish(addr, msg.encode())
