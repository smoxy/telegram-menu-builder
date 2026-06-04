"""Test suite for storage backends (MemoryStorage + BaseStorage contract)."""

import asyncio
import time as time_module

import pytest

from telegram_menu_builder.storage import MemoryStorage, StorageBackend


class TestMemoryStorage:
    """Tests for the in-memory storage backend."""

    @pytest.fixture
    def storage(self):
        """Provide a fresh storage instance for each test."""
        return MemoryStorage()

    async def test_set_get_round_trip(self, storage):
        """Data set can be retrieved unchanged."""
        await storage.set("k", {"value": 123})
        assert await storage.get("k") == {"value": 123}

    async def test_get_missing_returns_none(self, storage):
        """Missing keys return None."""
        assert await storage.get("nope") is None

    async def test_get_returns_a_copy(self, storage):
        """Mutating a returned dict must not affect stored data."""
        await storage.set("k", {"value": 1})
        retrieved = await storage.get("k")
        assert retrieved is not None
        retrieved["value"] = 999
        again = await storage.get("k")
        assert again == {"value": 1}

    async def test_set_stores_a_copy(self, storage):
        """Mutating the source dict after set must not affect stored data."""
        source = {"value": 1}
        await storage.set("k", source)
        source["value"] = 999
        assert await storage.get("k") == {"value": 1}

    async def test_ttl_expiry(self, storage, monkeypatch):
        """A key past its TTL is treated as missing and cleaned up."""
        await storage.set("k", {"value": 1}, ttl=60)
        assert await storage.exists("k") is True

        future = time_module.time() + 120
        monkeypatch.setattr("telegram_menu_builder.storage.memory.time.time", lambda: future)

        assert await storage.get("k") is None
        assert await storage.exists("k") is False

    async def test_delete(self, storage):
        """delete returns True when a key existed, False otherwise."""
        await storage.set("k", {"v": 1})
        assert await storage.delete("k") is True
        assert await storage.delete("k") is False

    async def test_add_set_if_absent(self, storage):
        """add stores and returns True the first time, False on a live repeat."""
        assert await storage.add("k", {"user_id": 1}) is True
        assert await storage.add("k", {"user_id": 2}) is False
        # The first write wins; the second add must not overwrite it.
        assert await storage.get("k") == {"user_id": 1}

    async def test_add_reclaims_expired_key(self, storage, monkeypatch):
        """An expired key is reclaimable: add succeeds again once the TTL elapses."""
        assert await storage.add("k", {"user_id": 1}, ttl=60) is True
        assert await storage.add("k", {"user_id": 2}, ttl=60) is False

        future = time_module.time() + 120
        monkeypatch.setattr("telegram_menu_builder.storage.memory.time.time", lambda: future)

        assert await storage.add("k", {"user_id": 3}, ttl=60) is True
        assert await storage.get("k") == {"user_id": 3}

    async def test_concurrent_add_exactly_one_winner(self, storage):
        """Concurrent add of the same key yields exactly one True (single winner)."""
        results = await asyncio.gather(
            storage.add("k", {"user_id": 1}),
            storage.add("k", {"user_id": 2}),
        )
        assert results.count(True) == 1
        assert results.count(False) == 1

    async def test_clear(self, storage):
        """clear removes all keys."""
        await storage.set("a", {"v": 1})
        await storage.set("b", {"v": 2})
        await storage.clear()
        assert await storage.keys() == []

    async def test_keys_with_pattern(self, storage):
        """keys supports glob-style filtering."""
        await storage.set("user:1", {"v": 1})
        await storage.set("user:2", {"v": 2})
        await storage.set("post:1", {"v": 3})

        assert set(await storage.keys()) == {"user:1", "user:2", "post:1"}
        assert set(await storage.keys("user:*")) == {"user:1", "user:2"}

    async def test_cleanup_expired(self, storage, monkeypatch):
        """cleanup_expired removes and counts expired keys."""
        await storage.set("a", {"v": 1}, ttl=60)
        await storage.set("b", {"v": 2})  # no ttl

        future = time_module.time() + 120
        monkeypatch.setattr("telegram_menu_builder.storage.memory.time.time", lambda: future)

        removed = await storage.cleanup_expired()
        assert removed == 1
        assert set(await storage.keys()) == {"b"}

    async def test_get_stats(self, storage):
        """get_stats reports counts about stored keys."""
        await storage.set("a", {"v": 1}, ttl=60)
        await storage.set("b", {"v": 2})

        stats = storage.get_stats()
        assert stats["total_keys"] == 2
        assert stats["keys_with_ttl"] == 1
        assert stats["active_keys"] == 2
        assert stats["expired_keys"] == 0

    async def test_operations_after_close_raise(self, storage):
        """Any operation after close() raises RuntimeError."""
        await storage.close()
        assert storage.is_closed is True
        with pytest.raises(RuntimeError, match="closed"):
            await storage.set("k", {"v": 1})

    async def test_async_context_manager_closes(self):
        """Exiting the async context manager closes the storage."""
        async with MemoryStorage() as storage:
            await storage.set("k", {"v": 1})
            assert storage.is_closed is False
        assert storage.is_closed is True

    def test_is_a_storage_backend(self, storage):
        """MemoryStorage satisfies the runtime-checkable StorageBackend protocol."""
        assert isinstance(storage, StorageBackend)
