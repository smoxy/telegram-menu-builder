"""Test suite for the SQLAlchemy storage backend (SQLAlchemyStorage)."""

import os
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("aiosqlite")

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from telegram_menu_builder.storage import SQLAlchemyStorage, StorageBackend

SQLITE_MEMORY_URL = "sqlite+aiosqlite:///:memory:"


class TestSQLAlchemyStorage:
    """Tests for the SQLAlchemy-backed storage backend (in-memory SQLite)."""

    @pytest.fixture
    async def storage(self):
        """Provide a fresh schema-initialized storage instance for each test."""
        store = SQLAlchemyStorage(database_url=SQLITE_MEMORY_URL)
        await store.create_schema()
        yield store
        await store.close()

    async def test_set_get_round_trip(self, storage):
        """Data set can be retrieved unchanged."""
        await storage.set("k", {"h": "menu", "p": {"value": 123}})
        assert await storage.get("k") == {"h": "menu", "p": {"value": 123}}

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
        """A key past its TTL is treated as missing on get/exists."""
        future = datetime.now(UTC) + timedelta(seconds=120)

        await storage.set("k", {"value": 1}, ttl=60)
        assert await storage.exists("k") is True

        monkeypatch.setattr(
            "telegram_menu_builder.storage.sqlalchemy._utcnow",
            lambda: future,
        )

        assert await storage.get("k") is None
        assert await storage.exists("k") is False

    async def test_delete(self, storage):
        """delete returns True when a key existed, False otherwise."""
        await storage.set("k", {"v": 1})
        assert await storage.delete("k") is True
        assert await storage.delete("k") is False

    async def test_clear(self, storage):
        """clear removes all keys."""
        await storage.set("a", {"v": 1})
        await storage.set("b", {"v": 2})
        await storage.clear()
        assert await storage.keys() == []

    async def test_keys_with_pattern(self, storage):
        """keys supports glob-style filtering translated to SQL LIKE."""
        await storage.set("user:1", {"v": 1})
        await storage.set("user:2", {"v": 2})
        await storage.set("post:1", {"v": 3})

        assert set(await storage.keys()) == {"user:1", "user:2", "post:1"}
        assert set(await storage.keys("user:*")) == {"user:1", "user:2"}

    async def test_cleanup_expired(self, storage, monkeypatch):
        """cleanup_expired removes and counts only expired keys."""
        future = datetime.now(UTC) + timedelta(seconds=120)

        await storage.set("a", {"v": 1}, ttl=60)
        await storage.set("b", {"v": 2})  # no ttl

        monkeypatch.setattr(
            "telegram_menu_builder.storage.sqlalchemy._utcnow",
            lambda: future,
        )

        removed = await storage.cleanup_expired()
        assert removed == 1
        assert set(await storage.keys()) == {"b"}

    async def test_get_stats(self, storage):
        """get_stats reports counts about stored keys (async here)."""
        await storage.set("a", {"v": 1}, ttl=60)
        await storage.set("b", {"v": 2})

        stats = await storage.get_stats()
        assert stats["total_keys"] == 2
        assert stats["keys_with_ttl"] == 1
        assert stats["active_keys"] == 2
        assert stats["expired_keys"] == 0

    async def test_set_same_key_overwrites(self, storage):
        """Re-setting the same key overwrites the value (upsert)."""
        await storage.set("k", {"h": "first", "p": {}})
        await storage.set("k", {"h": "second", "p": {"x": 1}})

        assert await storage.get("k") == {"h": "second", "p": {"x": 1}}
        assert set(await storage.keys()) == {"k"}

    async def test_set_same_key_refreshes_ttl(self, storage, monkeypatch):
        """Re-setting a key with a new TTL refreshes expiry (upsert)."""
        future = datetime.now(UTC) + timedelta(seconds=120)

        await storage.set("k", {"v": 1}, ttl=60)
        # Overwrite with no TTL -> the key should now be persistent.
        await storage.set("k", {"v": 2})

        monkeypatch.setattr(
            "telegram_menu_builder.storage.sqlalchemy._utcnow",
            lambda: future,
        )

        assert await storage.get("k") == {"v": 2}
        assert await storage.exists("k") is True

    async def test_fallback_upsert_for_unsupported_dialect(self, storage, monkeypatch):
        """An unsupported dialect routes set() through the DELETE-then-INSERT fallback."""
        # Force a dialect name that has no native UPSERT branch so set() must use
        # _fallback_set(). The underlying engine stays SQLite, so the DML executes.
        monkeypatch.setattr(storage._engine.dialect, "name", "oracle")

        # Initial insert via the fallback path.
        await storage.set("k", {"h": "first", "p": {}})
        assert await storage.get("k") == {"h": "first", "p": {}}

        # Re-setting the same key must overwrite (DELETE-then-INSERT), not duplicate.
        await storage.set("k", {"h": "second", "p": {"x": 1}})
        assert await storage.get("k") == {"h": "second", "p": {"x": 1}}
        assert set(await storage.keys()) == {"k"}

    async def test_create_schema_is_idempotent(self, storage):
        """create_schema can be called repeatedly without error."""
        await storage.create_schema()
        await storage.create_schema()
        await storage.set("k", {"v": 1})
        assert await storage.get("k") == {"v": 1}

    async def test_operations_after_close_raise(self, storage):
        """Any operation after close() raises RuntimeError."""
        await storage.close()
        assert storage.is_closed is True
        with pytest.raises(RuntimeError, match="closed"):
            await storage.set("k", {"v": 1})

    async def test_async_context_manager_closes(self):
        """Exiting the async context manager closes the storage."""
        store = SQLAlchemyStorage(database_url=SQLITE_MEMORY_URL)
        await store.create_schema()
        async with store as ctx:
            await ctx.set("k", {"v": 1})
            assert ctx.is_closed is False
        assert store.is_closed is True

    async def test_requires_database_url_or_engine(self):
        """Constructing with neither database_url nor engine raises ValueError."""
        with pytest.raises(ValueError, match="database_url"):
            SQLAlchemyStorage()

    async def test_accepts_existing_engine(self):
        """An existing AsyncEngine can be supplied via engine=."""
        engine = create_async_engine(
            SQLITE_MEMORY_URL,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        store = SQLAlchemyStorage(engine=engine)
        try:
            await store.create_schema()
            await store.set("k", {"v": 1})
            assert await store.get("k") == {"v": 1}
        finally:
            await store.close()
            # A borrowed engine must NOT be disposed by close(); it is still usable.
            await engine.dispose()

    def test_is_a_storage_backend(self):
        """SQLAlchemyStorage satisfies the runtime-checkable StorageBackend protocol."""
        store = SQLAlchemyStorage(database_url=SQLITE_MEMORY_URL)
        assert isinstance(store, StorageBackend)


@pytest.mark.integration
class TestSQLAlchemyStorageLiveDatabases:
    """Live integration tests for Postgres/MySQL upsert branches.

    Skipped by default. Set TMB_TEST_POSTGRES_URL and/or TMB_TEST_MYSQL_URL to a
    reachable async database URL (e.g. ``postgresql+asyncpg://...`` or
    ``mysql+aiomysql://...``) to exercise the dialect-specific UPSERT paths.
    """

    async def _round_trip(self, database_url: str) -> None:
        """Run schema setup, set/get, upsert overwrite, then drop schema."""
        store = SQLAlchemyStorage(database_url=database_url, table_name="menu_callbacks_it")
        try:
            await store.create_schema()
            await store.set("k", {"h": "first", "p": {}})
            assert await store.get("k") == {"h": "first", "p": {}}

            # Upsert: same key must overwrite.
            await store.set("k", {"h": "second", "p": {"x": 1}})
            assert await store.get("k") == {"h": "second", "p": {"x": 1}}

            await store.drop_schema()
        finally:
            await store.close()

    async def test_postgres_round_trip(self):
        """Exercise the PostgreSQL on_conflict_do_update branch."""
        url = os.environ.get("TMB_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("TMB_TEST_POSTGRES_URL not set")
        await self._round_trip(url)

    async def test_mysql_round_trip(self):
        """Exercise the MySQL on_duplicate_key_update branch."""
        url = os.environ.get("TMB_TEST_MYSQL_URL")
        if not url:
            pytest.skip("TMB_TEST_MYSQL_URL not set")
        await self._round_trip(url)
