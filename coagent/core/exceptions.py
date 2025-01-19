from __future__ import annotations

import json
import traceback

from pydantic import BaseModel, Field
from .messages import Error


class ErrorMeta(type):
    """Metaclass for automatically registering error classes.

    Note that `ErrorMeta` must inherit from `type`, otherwise when defining `BaseError` as below:

    ```python
    class BaseError(Exception, metaclass=ErrorMeta):
    ```

    there will be a metaclass conflict:

    ```
    TypeError: metaclass conflict: the metaclass of a derived class must be a (non-strict) subclass of the metaclasses of all its bases
    ```
    """

    registry = {}

    def __new__(mcls, name, bases, namespace, /, **kwargs):
        cls = super().__new__(mcls, name, bases, namespace, **kwargs)
        mcls.registry[cls.__name__] = cls
        return cls


class RawError(BaseModel):
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")


class BaseError(Exception, metaclass=ErrorMeta):
    def encode(self, mode: str = "python") -> dict:
        error = RawError(code=self.__class__.__name__, message=str(self))
        return error.model_dump(mode=mode)

    @classmethod
    def decode(cls, data: dict) -> BaseError:
        error = RawError.model_validate(data)
        error_class = cls.registry.get(error.code)
        if not error_class:
            raise ValueError(f"Unknown error code {error.code}")
        return error_class(error.message)

    def encode_json(self) -> str:
        data = self.encode(mode="json")
        return json.dumps(data)

    @classmethod
    def decode_json(cls, json_data: str | bytes) -> BaseError:
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON data")
        return cls.decode(data)

    def encode_message(self) -> Error:
        err = self.encode()
        return Error.model_validate(err)

    @classmethod
    def decode_message(cls, msg: Error) -> BaseError:
        err = msg.model_dump()
        return cls.decode(err)


class AgentTypeNotFoundError(BaseError):
    """Raised when the specified agent type in Address is not found."""


class SessionIDEmptyError(BaseError):
    """Raised when the session ID in Address is empty."""


class MessageDecodeError(BaseError):
    """Raised when the message cannot be decoded."""


class InternalError(BaseError):
    """Raised when an internal error occurs."""

    @classmethod
    def from_exception(
        cls, exc: BaseException, with_stack_trace: bool = True
    ) -> InternalError:
        if with_stack_trace:
            exc_info = "".join(traceback.format_exception(exc))
        else:
            exc_info = str(exc)
        return InternalError(exc_info)


class DeadlineExceededError(BaseError):
    """Raised when a context deadline is exceeded."""


class StreamError(BaseError):
    """Raised when the sender requests a non-streaming result but the receiver sends a stream."""
