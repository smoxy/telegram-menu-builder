"""Test suite for the SQLAlchemy storage backend (SQLAlchemyStorage)."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("aiosqlite")

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from telegram_menu_builder.storage import SQLAlchemyStorage, StorageBackend

SQLITE_MEMORY_URL = "sqlite+aiosqlite:///:memory:"


def _backend_params() -> list[Any]:
    """Backends to run the full suite against.

    SQLite (in-memory) always runs. PostgreSQL and/or MySQL are added — and
    marked ``integration`` — when their ``TMB_TEST_POSTGRES_URL`` /
    ``TMB_TEST_MYSQL_URL`` env vars point at a reachable async database, so the
    whole behavioral suite exercises the real dialects (UPSERT, ``get_stats``
    aggregation, ``LIKE`` patterns, TTL filtering) and not just SQLite.
    """
    params = [pytest.param(SQLITE_MEMORY_URL, id="sqlite")]
    postgres_url = os.environ.get("TMB_TEST_POSTGRES_URL")
    if postgres_url:
        params.append(pytest.param(postgres_url, id="postgres", marks=pytest.mark.integration))
    mysql_url = os.environ.get("TMB_TEST_MYSQL_URL")
    if mysql_url:
        params.append(pytest.param(mysql_url, id="mysql", marks=pytest.mark.integration))
    return params


class TestSQLAlchemyStorage:
    """Behavioral suite for the SQLAlchemy backend, run against every configured DB.

    The ``storage`` fixture is parametrized across SQLite and (when the
    ``TMB_TEST_*_URL`` env vars are set) live PostgreSQL/MySQL, so each test
    below validates the same observable contract on every supported dialect.
    """

    @pytest.fixture(params=_backend_params())
    async def storage(self, request):
        """Provide a fresh, schema-initialized backend for each test/dialect.

        The table is created and emptied on setup and dropped on teardown so
        tests stay isolated even on a shared, persistent real database.
        """
        store = SQLAlchemyStorage(database_url=request.param, table_name="tmb_test_callbacks")
        await store.create_schema()
        await store.clear()
        yield store
        try:
            if not store.is_closed:
                await store.drop_schema()
        finally:
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

    async def test_add_set_if_absent(self, storage):
        """add stores and returns True the first time, False on a live repeat."""
        assert await storage.add("k", {"user_id": 1}) is True
        assert await storage.add("k", {"user_id": 2}) is False
        # The first write wins; the second add must not overwrite it.
        assert await storage.get("k") == {"user_id": 1}

    async def test_add_reclaims_expired_row(self, storage, monkeypatch):
        """An expired row is reclaimable: add succeeds again once the TTL elapses."""
        future = datetime.now(UTC) + timedelta(seconds=120)

        assert await storage.add("k", {"user_id": 1}, ttl=60) is True
        assert await storage.add("k", {"user_id": 2}, ttl=60) is False

        monkeypatch.setattr(
            "telegram_menu_builder.storage.sqlalchemy._utcnow",
            lambda: future,
        )

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
