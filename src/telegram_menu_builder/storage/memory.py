"""In-memory storage backend implementation.

This module provides a simple in-memory storage backend suitable for testing
and applications that don't require persistent storage across restarts.
"""

import fnmatch
import time
from typing import Any

from telegram_menu_builder.storage.base import BaseStorage


class MemoryStorage(BaseStorage):
    """In-memory storage backend using Python dictionaries.

    This storage keeps all data in memory and supports TTL-based expiration.
    Data is lost when the process restarts.

    Attributes:
        _data: Internal dictionary storing the data
        _expiry: Dictionary mapping keys to expiration timestamps

    Example:
        >>> storage = MemoryStorage()
        >>> await storage.set("key1", {"value": 123}, ttl=60)
        >>> data = await storage.get("key1")
        >>> print(data)
        {'value': 123}

    Thread Safety:
        This implementation is NOT thread-safe. If you need concurrent access,
        consider using locks or a thread-safe storage backend.
    """

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        super().__init__()
        self._data: dict[str, dict[str, Any]] = {}
        self._expiry: dict[str, float] = {}

    async def set(self, key: str, data: dict[str, Any], ttl: int | None = None) -> None:
        """Store data in memory with optional TTL.

        Args:
            key: Unique identifier for the data
            data: Dictionary to store
            ttl: Time-to-live in seconds (None = no expiration)

        Raises:
            RuntimeError: If storage is closed
        """
        self._ensure_open()

        self._data[key] = data.copy()  # Store a copy to prevent external modifications

        if ttl is not None:
            self._expiry[key] = time.time() + ttl
        elif key in self._expiry:
            # Remove expiry if it existed before
            del self._expiry[key]

    async def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve data from memory.

        Args:
            key: Unique identifier for the data

        Returns:
            Stored dictionary or None if not found/expired

        Raises:
            RuntimeError: If storage is closed
        """
        self._ensure_open()

        # Check if key exists
        if key not in self._data:
            return None

        # Check if expired
        if key in self._expiry and time.time() > self._expiry[key]:
            # Expired - clean up and return None
            await self.delete(key)
            return None

        # Return a copy to prevent external modifications
        return self._data[key].copy()

    async def delete(self, key: str) -> bool:
        """Delete data from memory.

        Args:
            key: Unique identifier for the data

        Returns:
            True if deleted, False if not found

        Raises:
            RuntimeError: If storage is closed
        """
        self._ensure_open()

        existed = key in self._data

        if key in self._data:
            del self._data[key]

        if key in self._expiry:
            del self._expiry[key]

        return existed

    async def exists(self, key: str) -> bool:
        """Check if key exists in memory.

        Args:
            key: Unique identifier to check

        Returns:
            True if key exists and hasn't expired

        Raises:
            RuntimeError: If storage is closed
        """
        self._ensure_open()

        if key not in self._data:
            return False

        # Check expiration
        if key in self._expiry and time.time() > self._expiry[key]:
            # Expired - clean up
            await self.delete(key)
            return False

        return True

    async def clear(self) -> None:
        """Clear all data from memory.

        Raises:
            RuntimeError: If storage is closed
        """
        self._ensure_open()

        self._data.clear()
        self._expiry.clear()

    async def keys(self, pattern: str | None = None) -> list[str]:
        """Get all keys from memory, optionally filtered by pattern.

        Args:
            pattern: Optional glob-style pattern (supports * and ?)

        Returns:
            List of matching keys (excluding expired ones)

        Raises:
            RuntimeError: If storage is closed
        """
        self._ensure_open()

        # Clean up expired keys first
        current_time = time.time()
        expired_keys = [key for key, expiry in self._expiry.items() if current_time > expiry]

        for key in expired_keys:
            await self.delete(key)

        # Get all valid keys
        all_keys = list(self._data.keys())

        # Filter by pattern if provided
        if pattern is None:
            return all_keys

        # Simple glob pattern matching
        return [key for key in all_keys if fnmatch.fnmatch(key, pattern)]

    async def cleanup_expired(self) -> int:
        """Manually cleanup expired entries.

        This method is useful for periodic cleanup in long-running applications.

        Returns:
            Number of expired entries removed

        Raises:
            RuntimeError: If storage is closed
        """
        self._ensure_open()

        current_time = time.time()
        expired_keys = [key for key, expiry in self._expiry.items() if current_time > expiry]

        for key in expired_keys:
            await self.delete(key)

        return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dictionary with storage stats (total keys, expired keys, etc.)

        Raises:
            RuntimeError: If storage is closed
        """
        self._ensure_open()

        current_time = time.time()
        expired_count = sum(1 for expiry in self._expiry.values() if current_time > expiry)

        return {
            "total_keys": len(self._data),
            "keys_with_ttl": len(self._expiry),
            "expired_keys": expired_count,
            "active_keys": len(self._data) - expired_count,
        }

    async def close(self) -> None:
        """Close storage and free memory.

        After closing, the storage cannot be used anymore.
        """
        if not self._closed:
            self._data.clear()
            self._expiry.clear()
            await super().close()
