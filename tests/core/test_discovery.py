from coagent.core.discovery import DiscoveryQuery


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
