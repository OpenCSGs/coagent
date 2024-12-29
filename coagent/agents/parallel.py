from coagent.core import (
    Address,
    BaseAgent,
    Context,
    handler,
    GenericMessage,
    Message,
    RawMessage,
    SetReplyAgent,
)


class StartAggregation(Message):
    candidates: list[str]
    reply_addr: Address


class AggregationStatus(Message):
    status: str

    @property
    def busy(self) -> bool:
        return self.status == "busy"


class AggregationResult(Message):
    results: list[RawMessage]


class Aggregator(BaseAgent):
    def __init__(self):
        super().__init__()

        self._busy: bool = False
        self._data: StartAggregation | None = None
        self._result: AggregationResult | None = None

    @handler
    async def start_aggregation(
        self, msg: StartAggregation, ctx: Context
    ) -> AggregationStatus:
        if self._busy:
            return AggregationStatus(status="busy")

        self._busy = True
        self._data = msg
        self._result = AggregationResult(results=[])

        return AggregationStatus(status="ok")

    @handler
    async def handle(self, msg: GenericMessage, ctx: Context) -> None:
        if not self._busy:
            return

        self._result.results.append(msg.encode())

        if len(self._result.results) == len(self._data.candidates):
            if self._data.reply_addr:
                await self.channel.publish(self._data.reply_addr, self._result.encode())
            self._busy = False


class Parallel(BaseAgent):
    """Parallel is a composite agent that orchestrates its children agents
    concurrently and have their outputs aggregated by the given aggregator agent.
    """

    def __init__(self, *agent_types: str, aggregator: str = ""):
        super().__init__()
        self._agent_types = agent_types
        self._aggregator_type = aggregator

    async def started(self) -> None:
        aggregator_addr = Address(name=self._aggregator_type, id=self.address.id)
        # Make each agent reply to the aggregator agent.
        for agent_type in self._agent_types:
            addr = Address(name=agent_type, id=self.address.id)
            await self.channel.publish(
                addr,
                SetReplyAgent(address=aggregator_addr).encode(),
            )

    @handler
    async def handle(self, msg: GenericMessage, ctx: Context) -> None:
        if len(self._agent_types) == 0:
            return

        # Let the aggregator agent reply to the sending agent, if asked.
        reply_address = self.reply_address or msg.reply
        if reply_address:
            # Reset the reply address of the message, since it will be replied by the aggregator agent.
            msg.reply = None

        result = await self.channel.publish(
            Address(name=self._aggregator_type, id=self.address.id),
            StartAggregation(
                candidates=self._agent_types, reply_addr=reply_address
            ).encode(),
            request=True,
        )
        status = AggregationStatus.decode(result)
        if status.busy:
            return  # The aggregator agent is busy.

        for agent_type in self._agent_types:
            addr = Address(name=agent_type, id=self.address.id)
            await self.channel.publish(addr, msg.encode())
