from coagent.core.util import get_func_args


def func(a: int, b: str, c: float) -> None:
    pass


def test_get_func_args():
    assert get_func_args(func) == {"a", "b", "c"}
