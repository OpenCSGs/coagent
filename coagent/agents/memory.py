from typing import Protocol, runtime_checkable

from .messages import ChatMessage


@runtime_checkable
class Memory(Protocol):
    """Protocol for memory implementations.

    Memory stores conversation history for a specific agent, allowing
    agents to maintain context without requiring explicit manual memory management.
    """

    async def get_items(self, limit: int | None = None) -> list[ChatMessage]:
        """Retrieve the conversation history for this memory.

        Args:
            limit: Maximum number of items to retrieve. If None, retrieves all items.
                   When specified, returns the latest N items in chronological order.

        Returns:
            List of input items representing the conversation history
        """
        ...

    async def add_items(self, *items: ChatMessage) -> None:
        """Add new items to the conversation history.

        Args:
            items: List of input items to add to the history
        """
        ...

    async def pop_item(self) -> ChatMessage | None:
        """Remove and return the most recent item from the memory.

        Returns:
            The most recent item if it exists, None if the memory is empty
        """
        ...

    async def clear_items(self) -> None:
        """Clear all items for this memory."""
        ...


class NoMemory(list):
    """Built-in memory implementation that stores no conversation history."""

    async def get_items(self, limit: int | None = None) -> list[ChatMessage]:
        """Retrieve the conversation history for this memory."""
        return []

    async def add_items(self, *items: ChatMessage) -> None:
        """Add new items to the conversation history."""
        return

    async def pop_item(self) -> ChatMessage | None:
        """Remove and return the most recent item from the memory."""
        return

    async def clear_items(self) -> None:
        """Clear all items for this memory."""
        return


class InMemMemory(list):
    """Built-in memory implementation that stores conversation history in memory."""

    async def get_items(self, limit: int | None = None) -> list[ChatMessage]:
        """Retrieve the conversation history for this memory."""
        if limit is None:
            return self
        # Return the latest limit number of items.
        return self[-limit:]

    async def add_items(self, *items: ChatMessage) -> None:
        """Add new items to the conversation history."""
        self.extend(items)

    async def pop_item(self) -> ChatMessage | None:
        """Remove and return the most recent item from the memory."""
        if not self:
            return None
        return self.pop()

    async def clear_items(self) -> None:
        """Clear all items for this memory."""
        self.clear()
