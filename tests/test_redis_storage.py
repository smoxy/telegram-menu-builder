"""Test suite for the Redis/Valkey storage backend (RedisStorage).

A single :class:`RedisStorage` (built on redis-py's async client) targets both
Redis and Valkey: because Valkey speaks the same RESP wire protocol, the same
client class connects unchanged when the URL is pointed at a Valkey server.

The behavioral suite is parametrized over backends, mirroring ``_backend_params``
in ``test_sql_storage.py``:

* ``fakeredis`` always runs in-process (no server required).
* a live Redis server runs (and is marked ``integration``) when
  ``TMB_TEST_REDIS_URL`` is set.
* a live Valkey server runs (and is marked ``integration``) when
  ``TMB_TEST_VALKEY_URL`` is set.
"""

import asyncio
import os
from typing import Any

import pytest

pytest.importorskip("redis")
pytest.importorskip("fakeredis")

import fakeredis.aioredis

from telegram_menu_builder.storage import RedisStorage, StorageBackend

NAMESPACE = "tmbtest:"


def _backend_params() -> list[Any]:
    """Backends to run the full suite against.

    ``fakeredis`` always runs (in-process). A live Redis and/or Valkey server is
    added — and marked ``integration`` — when ``TMB_TEST_REDIS_URL`` /
    ``TMB_TEST_VALKEY_URL`` point at a reachable async server, so the whole
    behavioral suite exercises the real servers (SCAN MATCH, native TTL) and not
    just the in-memory fake.

    Each param is a ``(kind, value)`` record telling the fixture how to build the
    store: ``("fake", None)`` builds a ``FakeRedis`` client and passes it via
    ``client=`` (borrowed); ``("url", url)`` constructs the store from ``url=``
    (owned).
    """
    params = [pytest.param(("fake", None), id="fakeredis")]
    redis_url = os.environ.get("TMB_TEST_REDIS_URL")
    if redis_url:
        params.append(pytest.param(("url", redis_url), id="redis", marks=pytest.mark.integration))
    valkey_url = os.environ.get("TMB_TEST_VALKEY_URL")
    if valkey_url:
        params.append(pytest.param(("url", valkey_url), id="valkey", marks=pytest.mark.integration))
    return params


class TestRedisStorage:
    """Behavioral suite for the Redis/Valkey backend, run against every configured server.

    The ``storage`` fixture is parametrized across the in-process fake and (when
    the ``TMB_TEST_*_URL`` env vars are set) live Redis/Valkey, so each test below
    validates the same observable contract on every supported server.
    """

    @pytest.fixture(params=_backend_params())
    async def storage(self, request):
        """Provide a fresh, namespace-isolated backend for each test/server.

        The namespace is cleared on setup and teardown so tests stay isolated even
        on a shared, persistent real server, then the store is closed.

        For the ``fake`` param a ``FakeRedis`` client is created and passed via
        ``client=`` (BORROWED, so ``store.close()`` does not close it); the fixture
        closes the fake client itself in teardown. For ``url`` params the store
        owns the client created from the URL.
        """
        kind, value = request.param
        fake_client = None
        if kind == "fake":
            fake_client = fakeredis.aioredis.FakeRedis()
            store = RedisStorage(client=fake_client, namespace=NAMESPACE)
        else:
            store = RedisStorage(url=value, namespace=NAMESPACE)

        await store.clear()
        try:
            yield store
        finally:
            try:
                if not store.is_closed:
                    await store.clear()
                    await store.close()
            finally:
                if fake_client is not None:
                    await fake_client.aclose()

    async def test_set_get_round_trip(self, storage):
        """Data set can be retrieved unchanged."""
        await storage.set("k", {"h": "menu", "p": {"value": 123}})
        assert await storage.get("k") == {"h": "menu", "p": {"value": 123}}

    async def test_get_missing_returns_none(self, storage):
        """Missing keys return None (never raises)."""
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

    async def test_delete(self, storage):
        """delete returns True when a key existed, False otherwise."""
        await storage.set("k", {"v": 1})
        assert await storage.delete("k") is True
        assert await storage.delete("k") is False

    async def test_clear(self, storage):
        """clear removes all keys in the namespace."""
        await storage.set("a", {"v": 1})
        await storage.set("b", {"v": 2})
        await storage.clear()
        assert await storage.keys() == []

    async def test_keys_with_pattern(self, storage):
        """keys supports SCAN MATCH glob filtering and strips the namespace."""
        await storage.set("user:1", {"v": 1})
        await storage.set("user:2", {"v": 2})
        await storage.set("post:1", {"v": 3})

        assert set(await storage.keys()) == {"user:1", "user:2", "post:1"}
        assert set(await storage.keys("user:*")) == {"user:1", "user:2"}

    async def test_exists(self, storage):
        """exists returns True for present keys and False otherwise."""
        await storage.set("k", {"v": 1})
        assert await storage.exists("k") is True
        assert await storage.exists("nope") is False

    async def test_set_same_key_overwrites(self, storage):
        """Re-setting the same key overwrites the value (dedup-friendly)."""
        await storage.set("k", {"h": "first", "p": {}})
        await storage.set("k", {"h": "second", "p": {"x": 1}})

        assert await storage.get("k") == {"h": "second", "p": {"x": 1}}
        assert set(await storage.keys()) == {"k"}

    async def test_ttl_registration(self, storage):
        """set(ttl=...) registers a server-side TTL; set without ttl is persistent.

        This verifies OUR code passes ``ex`` correctly to the client; the server
        enforces the actual expiry.
        """
        await storage.set("k", {"v": 1}, ttl=60)
        remaining = await storage.client.ttl(storage._k("k"))
        assert 0 < remaining <= 60

        await storage.set("persistent", {"v": 2})
        assert await storage.client.ttl(storage._k("persistent")) == -1

    async def test_overwrite_clears_ttl(self, storage):
        """Re-setting a key with no ttl removes a previously registered expiry."""
        await storage.set("k", {"v": 1}, ttl=60)
        assert 0 < await storage.client.ttl(storage._k("k")) <= 60
        await storage.set("k", {"v": 2})
        assert await storage.client.ttl(storage._k("k")) == -1

    async def test_namespace_isolation(self, storage):
        """Two stores over the SAME client but DIFFERENT namespaces are isolated.

        Neither store sees the other's keys, and clear() on one leaves the other
        intact.
        """
        other = RedisStorage(client=storage.client, namespace="tmbtest-other:")
        try:
            await other.clear()
            await storage.set("shared", {"v": "ns-a"})
            await other.set("shared", {"v": "ns-b"})

            # Each namespace sees only its own value.
            assert await storage.get("shared") == {"v": "ns-a"}
            assert await other.get("shared") == {"v": "ns-b"}
            assert await storage.keys() == ["shared"]
            assert await other.keys() == ["shared"]

            # clear() is namespace-scoped: clearing one leaves the other intact.
            await storage.clear()
            assert await storage.keys() == []
            assert await other.get("shared") == {"v": "ns-b"}
        finally:
            await other.clear()
            # other BORROWS the client; closing it must not close the shared client.
            await other.close()

    async def test_operations_after_close_raise(self, storage):
        """Any operation after close() raises RuntimeError."""
        await storage.close()
        assert storage.is_closed is True
        with pytest.raises(RuntimeError, match="closed"):
            await storage.set("k", {"v": 1})

    async def test_borrowed_client_not_closed_by_close(self):
        """A borrowed client is NOT closed by store.close() and stays usable."""
        client = fakeredis.aioredis.FakeRedis()
        store = RedisStorage(client=client, namespace=NAMESPACE)
        try:
            await store.set("k", {"v": 1})
            await store.close()
            assert store.is_closed is True

            # The borrowed client is still usable after the store closed.
            await client.set("raw", "still-alive")
            assert await client.get("raw") in (b"still-alive", "still-alive")
        finally:
            await client.flushall()
            await client.aclose()

    async def test_async_context_manager_closes(self):
        """Exiting the async context manager closes the storage."""
        client = fakeredis.aioredis.FakeRedis()
        try:
            store = RedisStorage(client=client, namespace=NAMESPACE)
            async with store as ctx:
                await ctx.set("k", {"v": 1})
                assert ctx.is_closed is False
            assert store.is_closed is True
        finally:
            await client.flushall()
            await client.aclose()

    async def test_requires_url_or_client(self):
        """Constructing with neither url nor client raises ValueError."""
        with pytest.raises(ValueError, match="url"):
            RedisStorage()

    async def test_rejects_both_url_and_client(self):
        """Constructing with both url and client raises ValueError."""
        client = fakeredis.aioredis.FakeRedis()
        try:
            with pytest.raises(ValueError, match="client"):
                RedisStorage(url="redis://localhost:6379/0", client=client)
        finally:
            await client.aclose()

    async def test_encoder_round_trip_through_redis(self):
        """A forced-strategy MenuAction round-trips through RedisStorage(fake)."""
        from telegram_menu_builder.encoding import CallbackEncoder
        from telegram_menu_builder.types import MenuAction, StorageStrategy

        client = fakeredis.aioredis.FakeRedis()
        store = RedisStorage(client=client, namespace=NAMESPACE)
        try:
            encoder = CallbackEncoder(store)
            action = MenuAction(handler="edit_user", params={"user_id": 123, "field": "email"})

            encoded = await encoder.encode(action, force_strategy=StorageStrategy.PERSISTENT)
            decoded = await encoder.decode(encoded)

            assert decoded.handler == "edit_user"
            assert decoded.params == {"user_id": 123, "field": "email"}
        finally:
            await store.clear()
            await store.close()
            await client.aclose()

    def test_is_a_storage_backend(self):
        """RedisStorage satisfies the runtime-checkable StorageBackend protocol."""
        client = fakeredis.aioredis.FakeRedis()
        store = RedisStorage(client=client, namespace=NAMESPACE)
        assert isinstance(store, StorageBackend)


@pytest.mark.integration
class TestRedisStorageLiveExpiry:
    """Live-only tests that exercise real server-side TTL expiry.

    These run only when a live URL is set; they sleep on the wall clock, so they
    are kept OUT of the fast fakeredis path.
    """

    @pytest.fixture(
        params=[
            param
            for param in (
                pytest.param(os.environ.get("TMB_TEST_REDIS_URL"), id="redis"),
                pytest.param(os.environ.get("TMB_TEST_VALKEY_URL"), id="valkey"),
            )
            if param.values[0]
        ]
        or [pytest.param(None, id="no-live-server", marks=pytest.mark.skip)]
    )
    async def live_storage(self, request):
        """Provide a live (owned) backend, isolated by namespace, for expiry tests."""
        store = RedisStorage(url=request.param, namespace=NAMESPACE)
        await store.clear()
        try:
            yield store
        finally:
            if not store.is_closed:
                await store.clear()
                await store.close()

    async def test_real_expiry(self, live_storage):
        """A key set with a short TTL really disappears after the TTL elapses."""
        await live_storage.set("k", {"v": 1}, ttl=1)
        assert await live_storage.exists("k") is True

        await asyncio.sleep(1.2)

        assert await live_storage.get("k") is None
        assert await live_storage.exists("k") is False
