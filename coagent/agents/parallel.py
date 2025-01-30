from typing import Awaitable, Callable
from coagent.core import (
    Address,
    BaseAgent,
    Context,
    handler,
    GenericMessage,
    Message,
    NO_REPLY,
    RawMessage,
    Reply,
    SetReplyInfo,
)


class StartAggregation(Message):
    candidates: list[str]
    reply_info: Reply | None


class AggregationStatus(Message):
    status: str

    @property
    def busy(self) -> bool:
        return self.status == "busy"


class AggregationResult(Message):
    results: list[RawMessage]


class Aggregator(BaseAgent):
    def __init__(
        self,
        aggregate: Callable[[list[RawMessage]], Awaitable[RawMessage]] | None = None,
    ):
        super().__init__()

        self._aggregate = aggregate or self.aggregate

        self._busy: bool = False
        self._data: StartAggregation | None = None
        self._results: list[RawMessage] | None = None

    @handler
    async def start_aggregation(
        self, msg: StartAggregation, ctx: Context
    ) -> AggregationStatus:
        if self._busy:
            return AggregationStatus(status="busy")

        self._busy = True
        self._data = msg
        self._results = []

        return AggregationStatus(status="ok")

    @handler
    async def handle(self, msg: GenericMessage, ctx: Context) -> None:
        if not self._busy:
            return

        self._results.append(msg.encode())

        if len(self._results) == len(self._data.candidates):
            if self._data.reply_info:
                result = await self._aggregate(self._results)
                await self.send_reply(self._data.reply_info, result)
            self._busy = False

    async def aggregate(self, results: list[RawMessage]) -> Message:
        """Aggregate the results to a single one.

        Override this method to provide custom aggregation logic.
        """
        return AggregationResult(results=results)


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
        aggregator_reply = Reply(address=aggregator_addr)
        # Make each agent reply to the aggregator agent.
        for agent_type in self._agent_types:
            addr = Address(name=agent_type, id=self.address.id)
            await self.channel.publish(
                addr,
                SetReplyInfo(reply_info=aggregator_reply).encode(),
            )

        # Set the current agent to no-reply mode.
        await self._set_reply_info(NO_REPLY)

    @handler
    async def handle(self, msg: GenericMessage, ctx: Context) -> None:
        if len(self._agent_types) == 0:
            raise RuntimeError("No agent types provided.")

        # Let the aggregator agent reply to the sending agent, if asked.
        reply = msg.reply
        result = await self.channel.publish(
            Address(name=self._aggregator_type, id=self.address.id),
            StartAggregation(candidates=self._agent_types, reply_info=reply).encode(),
            request=True,
        )
        status = AggregationStatus.decode(result)
        if status.busy:
            # The aggregator agent is busy.
            raise RuntimeError("Parallel agent is busy.")

        for agent_type in self._agent_types:
            addr = Address(name=agent_type, id=self.address.id)
            await self.channel.publish(addr, msg.encode())
