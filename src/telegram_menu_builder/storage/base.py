"""Storage backend interface and abstract base class.

This module defines the protocol that all storage backends must implement,
allowing for pluggable storage strategies (memory, Redis, SQL, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Protocol defining the interface for storage backends.

    All storage implementations must provide these methods to be compatible
    with the menu builder system.

    Example:
        >>> class MyStorage:
        ...     async def set(self, key: str, data: dict[str, Any], ttl: int | None = None) -> None:
        ...         # Implementation
        ...         pass
        ...
        ...     async def get(self, key: str) -> dict[str, Any] | None:
        ...         # Implementation
        ...         pass
        ...
        ...     async def delete(self, key: str) -> bool:
        ...         # Implementation
        ...         pass
    """

    async def set(self, key: str, data: dict[str, Any], ttl: int | None = None) -> None:
        """Store data with an optional TTL.

        Args:
            key: Unique identifier for the data
            data: Dictionary to store (must be JSON-serializable)
            ttl: Time-to-live in seconds (None = no expiration)

        Raises:
            StorageError: If storage operation fails
        """
        ...

    async def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve data by key.

        Args:
            key: Unique identifier for the data

        Returns:
            Stored dictionary or None if not found/expired

        Raises:
            StorageError: If retrieval operation fails
        """
        ...

    async def delete(self, key: str) -> bool:
        """Delete data by key.

        Args:
            key: Unique identifier for the data

        Returns:
            True if deleted, False if not found

        Raises:
            StorageError: If deletion operation fails
        """
        ...

    async def exists(self, key: str) -> bool:
        """Check if key exists in storage.

        Args:
            key: Unique identifier to check

        Returns:
            True if key exists and hasn't expired
        """
        ...

    async def clear(self) -> None:
        """Clear all stored data.

        Warning:
            This will delete ALL data in the storage backend.
            Use with caution in production environments.

        Raises:
            StorageError: If clear operation fails
        """
        ...

    async def keys(self, pattern: str | None = None) -> list[str]:
        """Get all keys, optionally filtered by pattern.

        Args:
            pattern: Optional pattern for filtering keys (implementation-specific)

        Returns:
            List of matching keys

        Raises:
            StorageError: If operation fails
        """
        ...


class BaseStorage(ABC):
    """Abstract base class for storage backends with common functionality.

    This class provides a template and shared utilities for storage implementations.
    Subclasses only need to implement the abstract methods.
    """

    def __init__(self) -> None:
        """Initialize storage backend."""
        self._closed = False

    @abstractmethod
    async def set(self, key: str, data: dict[str, Any], ttl: int | None = None) -> None:
        """Store data with an optional TTL."""

    @abstractmethod
    async def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve data by key."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete data by key."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""

    @abstractmethod
    async def clear(self) -> None:
        """Clear all stored data."""

    @abstractmethod
    async def keys(self, pattern: str | None = None) -> list[str]:
        """Get all keys, optionally filtered by pattern."""

    async def close(self) -> None:
        """Close storage backend and cleanup resources.

        Override this method if your storage needs cleanup (connections, files, etc.).
        """
        self._closed = True

    @property
    def is_closed(self) -> bool:
        """Check if storage is closed."""
        return self._closed

    def _ensure_open(self) -> None:
        """Ensure storage is not closed.

        Raises:
            RuntimeError: If storage is closed
        """
        if self._closed:
            raise RuntimeError(f"{self.__class__.__name__} is closed")

    async def __aenter__(self) -> "BaseStorage":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
