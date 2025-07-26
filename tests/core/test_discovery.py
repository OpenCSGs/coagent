from coagent.core.discovery import DiscoveryBatchQuery, DiscoveryQuery, DiscoveryServer
from coagent.core.types import AgentSpec, Address, new
from coagent.core.agent import BaseAgent, Context

import pytest


class TestDiscoveryQuery:
    def test_matches(self):
        # Query with empty namespace should match any name.
        query = DiscoveryQuery(namespace="")
        assert query.matches("test") is True

        # Non-inclusive mode.
        query = DiscoveryQuery(namespace="test")
        assert query.matches("test") is False

        # Inclusive mode.
        query = DiscoveryQuery(namespace="test", inclusive=True)
        assert query.matches("test") is True

        # Non-recursive mode.
        query = DiscoveryQuery(namespace="test")
        assert query.matches("test.a") is True
        assert query.matches("test.a.b") is False

        # Recursive mode.
        query = DiscoveryQuery(namespace="test", recursive=True)
        assert query.matches("test.a.b") is True


class MockAgent(BaseAgent):
    pass


class TestDiscoveryServer:
    async def register_agents(self, server: DiscoveryServer, *names: str):
        for name in names:
            await server.register(AgentSpec(name=name, constructor=new(MockAgent)))

    @pytest.mark.asyncio
    async def test_search(self):
        server = DiscoveryServer()
        server.address = Address(name="discovery.server", id="")
        await self.register_agents(
            server,
            "a",
            "a.x",
            "a.x.0",
            "a.y",
            "a.y.0",
            "b",
            "b.x",
            "b.y",
            "b.z.0",
        )

        # Case 1
        reply = await server._search(
            DiscoveryQuery(namespace="", recursive=False), Context()
        )
        assert [a.name for a in reply.agents] == ["a", "b"]

        # Case 2
        reply = await server._search(
            DiscoveryQuery(namespace="", recursive=True), Context()
        )
        assert [a.name for a in reply.agents] == [
            "a",
            "a.x",
            "a.x.0",
            "a.y",
            "a.y.0",
            "b",
            "b.x",
            "b.y",
            "b.z.0",
        ]

        # Case 3
        reply = await server._search(
            DiscoveryQuery(namespace="a", recursive=False), Context()
        )
        assert [a.name for a in reply.agents] == ["a.x", "a.y"]

        # Case 4
        reply = await server._search(
            DiscoveryQuery(namespace="a", recursive=True), Context()
        )
        assert [a.name for a in reply.agents] == [
            "a.x",
            "a.x.0",
            "a.y",
            "a.y.0",
        ]

        # Case 5
        reply = await server._search(
            DiscoveryQuery(namespace="b", recursive=False), Context()
        )
        assert [a.name for a in reply.agents] == ["b.x", "b.y"]

        # Case 6
        reply = await server._search(
            DiscoveryQuery(namespace="b", recursive=True), Context()
        )
        assert [a.name for a in reply.agents] == [
            "b.x",
            "b.y",
            "b.z.0",
        ]

    @pytest.mark.asyncio
    async def test_batch_search(self):
        server = DiscoveryServer()
        server.address = Address(name="discovery.server", id="")
        await self.register_agents(
            server,
            "a",
            "a.x",
            "a.x.0",
            "a.y",
            "a.y.0",
            "b",
            "b.x",
            "b.y",
            "b.z.0",
        )

        batch_reply = await server.batch_search(
            DiscoveryBatchQuery(
                queries=[
                    DiscoveryQuery(namespace="a", recursive=False),
                    DiscoveryQuery(namespace="b", recursive=False),
                ]
            ),
            Context(),
        )
        assert [[a.name for a in r.agents] for r in batch_reply.replies] == [
            ["a.x", "a.y"],
            ["b.x", "b.y"],
        ]
