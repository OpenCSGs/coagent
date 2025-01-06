from coagent.core.util import Trie, get_func_args


class TestTrie:
    def test_direct_items(self):
        trie = Trie(separator=".")
        trie["test"] = 1
        trie["test.a"] = 2
        trie["test.b"] = 3
        trie["test.a.b"] = 4
        trie["test.a.b.c"] = 5

        assert trie.direct_items("test") == [("test", 1), ("test.a", 2), ("test.b", 3)]
        assert trie.direct_items("test.a") == [("test.a", 2), ("test.a.b", 4)]
        assert trie.direct_items("test.a.b") == [("test.a.b", 4), ("test.a.b.c", 5)]
        assert trie.direct_items("test.a.b.c") == [("test.a.b.c", 5)]


def test_get_func_args():
    def func(a: int, b: str, c: float) -> None:
        pass

    assert get_func_args(func) == {"a", "b", "c"}
