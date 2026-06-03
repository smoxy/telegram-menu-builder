# Custom Storage Backends

The built-in [`MemoryStorage`](../guide/storage.md) is single-process and loses
data on restart. For production bots — or anything multi-process — you supply a
custom backend. There are two ways to do it:

1. **Satisfy the [`StorageBackend`][telegram_menu_builder.StorageBackend]
   Protocol.** Implement the required `async` methods on any class; no
   inheritance needed. The Protocol is `runtime_checkable`, so
   `isinstance(obj, StorageBackend)` works.
2. **Subclass `BaseStorage`.** You inherit `close()`, `is_closed`,
   `_ensure_open()`, and the async context-manager protocol, and only implement
   the abstract data methods.

Either object can be passed to `MenuBuilder(storage=...)` and
`MenuRouter(storage=...)`.

!!! warning "Share one instance between builder and router"
    The builder writes payloads; the router reads them. Pass the **same** backend
    instance to both, or large callbacks will fail to decode. See
    [Storage](../guide/storage.md#storage) for the shared-instance pattern.

## Method contract

A backend must implement these six methods (plus an optional `close`):

| Method | Signature | Contract |
| --- | --- | --- |
| `set` | `async set(key, data, ttl=None) -> None` | Store `data` under `key`. `ttl` is seconds; `None` means no expiry. |
| `get` | `async get(key) -> dict \| None` | Return the stored dict, or `None` if missing/expired. |
| `delete` | `async delete(key) -> bool` | Remove `key`; return `True` if it existed. |
| `exists` | `async exists(key) -> bool` | `True` if `key` exists and has not expired. |
| `clear` | `async clear() -> None` | Remove everything. Use with care. |
| `keys` | `async keys(pattern=None) -> list[str]` | All keys, optionally filtered (implementation-defined pattern). |
| `close` | `async close() -> None` | Release resources (connections, files). Optional but recommended. |

!!! note "Two invariants to respect"
    1. **Stored values are JSON-serializable dicts** (the encoder always passes a
       `{"h": ..., "p": ...}` dict). Serialize with `json.dumps` on `set` and
       `json.loads` on `get`.
    2. **Return copies, not live references.** `get` must not hand back an object
       that the caller can mutate in place and thereby corrupt your store.
       `MemoryStorage` calls `data.copy()` on both `set` and `get` for this
       reason; backends that round-trip through JSON get this for free.

## Subclassing BaseStorage

`BaseStorage` provides lifecycle plumbing so you only write the data methods.
Call `self._ensure_open()` at the top of each method to honour `close()`.

```python
from typing import Any

from telegram_menu_builder.storage import BaseStorage  # re-exported below

class MyStorage(BaseStorage):
    def __init__(self) -> None:
        super().__init__()
        # set up your connection / client here

    async def set(self, key: str, data: dict[str, Any], ttl: int | None = None) -> None:
        self._ensure_open()
        ...

    async def get(self, key: str) -> dict[str, Any] | None:
        self._ensure_open()
        ...

    async def delete(self, key: str) -> bool:
        self._ensure_open()
        ...

    async def exists(self, key: str) -> bool:
        self._ensure_open()
        ...

    async def clear(self) -> None:
        self._ensure_open()
        ...

    async def keys(self, pattern: str | None = None) -> list[str]:
        self._ensure_open()
        ...

    async def close(self) -> None:
        if not self.is_closed:
            # tear down your connection here
            await super().close()
```

!!! note "Importing BaseStorage"
    `MemoryStorage` and the `StorageBackend` Protocol are exported from
    `telegram_menu_builder.storage`. `BaseStorage` lives in
    `telegram_menu_builder.storage.base` and can be imported from there if it is
    not re-exported in your installed version.

## Redis sketch

Redis is a natural fit: it has native TTL support, so the `ttl` argument maps
straight onto `SETEX`/`expire`. Store values as JSON strings.

```python
import json
from typing import Any

from redis.asyncio import Redis

from telegram_menu_builder.storage.base import BaseStorage

class RedisStorage(BaseStorage):
    def __init__(self, redis: Redis, namespace: str = "tmb:") -> None:
        super().__init__()
        self._redis = redis
        self._ns = namespace

    def _k(self, key: str) -> str:
        return f"{self._ns}{key}"

    async def set(self, key: str, data: dict[str, Any], ttl: int | None = None) -> None:
        self._ensure_open()
        payload = json.dumps(data, separators=(",", ":"))
        if ttl is not None:
            await self._redis.set(self._k(key), payload, ex=ttl)
        else:
            await self._redis.set(self._k(key), payload)

    async def get(self, key: str) -> dict[str, Any] | None:
        self._ensure_open()
        raw = await self._redis.get(self._k(key))
        if raw is None:
            return None
        # json.loads produces a fresh dict, so callers cannot mutate our store.
        return json.loads(raw)

    async def delete(self, key: str) -> bool:
        self._ensure_open()
        return await self._redis.delete(self._k(key)) > 0

    async def exists(self, key: str) -> bool:
        self._ensure_open()
        return await self._redis.exists(self._k(key)) > 0

    async def clear(self) -> None:
        self._ensure_open()
        async for k in self._redis.scan_iter(match=f"{self._ns}*"):
            await self._redis.delete(k)

    async def keys(self, pattern: str | None = None) -> list[str]:
        self._ensure_open()
        match = f"{self._ns}{pattern}" if pattern else f"{self._ns}*"
        found = [k async for k in self._redis.scan_iter(match=match)]
        # Strip the namespace so callers see the same keys they stored.
        return [k.decode().removeprefix(self._ns) for k in found]

    async def close(self) -> None:
        if not self.is_closed:
            await self._redis.aclose()
            await super().close()
```

!!! note "Let Redis enforce TTL"
    Don't track expiry yourself — pass `ex=ttl` and let Redis expire the key.
    `get`/`exists` then never see stale data.

## SQL / aiosqlite sketch

SQL backends have no built-in TTL, so store an absolute expiry timestamp
alongside the payload and check it on read. Persistent entries (`ttl is None`)
get a `NULL` expiry.

```python
import json
import time
from typing import Any

import aiosqlite

from telegram_menu_builder.storage.base import BaseStorage

class SQLiteStorage(BaseStorage):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__()
        self._db = db

    @classmethod
    async def create(cls, path: str = ":memory:") -> "SQLiteStorage":
        db = await aiosqlite.connect(path)
        await db.execute(
            "CREATE TABLE IF NOT EXISTS callbacks ("
            "  key TEXT PRIMARY KEY,"
            "  data TEXT NOT NULL,"
            "  expires_at REAL"  # NULL = never expires
            ")"
        )
        await db.commit()
        return cls(db)

    async def set(self, key: str, data: dict[str, Any], ttl: int | None = None) -> None:
        self._ensure_open()
        expires_at = time.time() + ttl if ttl is not None else None
        await self._db.execute(
            "INSERT INTO callbacks(key, data, expires_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET data=excluded.data, expires_at=excluded.expires_at",
            (key, json.dumps(data, separators=(",", ":")), expires_at),
        )
        await self._db.commit()

    async def get(self, key: str) -> dict[str, Any] | None:
        self._ensure_open()
        async with self._db.execute(
            "SELECT data, expires_at FROM callbacks WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        data, expires_at = row
        if expires_at is not None and time.time() > expires_at:
            await self.delete(key)
            return None
        return json.loads(data)

    async def delete(self, key: str) -> bool:
        self._ensure_open()
        cur = await self._db.execute("DELETE FROM callbacks WHERE key = ?", (key,))
        await self._db.commit()
        return cur.rowcount > 0

    async def exists(self, key: str) -> bool:
        self._ensure_open()
        return await self.get(key) is not None

    async def clear(self) -> None:
        self._ensure_open()
        await self._db.execute("DELETE FROM callbacks")
        await self._db.commit()

    async def keys(self, pattern: str | None = None) -> list[str]:
        self._ensure_open()
        if pattern is None:
            query, args = "SELECT key FROM callbacks", ()
        else:
            # Translate a glob '*' into SQL LIKE '%'.
            query, args = "SELECT key FROM callbacks WHERE key LIKE ?", (pattern.replace("*", "%"),)
        async with self._db.execute(query, args) as cur:
            return [r[0] for r in await cur.fetchall()]

    async def close(self) -> None:
        if not self.is_closed:
            await self._db.close()
            await super().close()
```

!!! warning "Expire lazily and/or sweep"
    The sketch above expires on read. For a busy bot, also run a periodic
    `DELETE FROM callbacks WHERE expires_at IS NOT NULL AND expires_at < ?` so
    expired short-term rows don't accumulate.

## Testing tips

You can exercise a custom backend without a live server:

- **Redis** — use [`fakeredis`](https://github.com/cunla/fakeredis-py) with its
  async client (`fakeredis.aioredis.FakeRedis`). It speaks the same async API as
  `redis.asyncio`, including TTL.
- **SQL** — use an in-memory SQLite database (`aiosqlite.connect(":memory:")`),
  as in the sketch's `create(":memory:")`.

Round-trip every method against the contract: `set` then `get`, expiry honoured,
`delete` returns the right boolean, `keys` filtering, and `clear`. Crucially,
verify that mutating a dict returned by `get` does **not** change what a second
`get` returns — that is the "return copies" invariant.

```python
import pytest

class TestRedisStorage:
    @pytest.fixture
    async def storage(self):
        import fakeredis.aioredis
        backend = RedisStorage(fakeredis.aioredis.FakeRedis())
        yield backend
        await backend.close()

    async def test_set_get_roundtrip(self, storage):
        await storage.set("k", {"h": "edit", "p": {"id": 1}}, ttl=60)
        assert await storage.get("k") == {"h": "edit", "p": {"id": 1}}

    async def test_returns_copies(self, storage):
        await storage.set("k", {"h": "edit", "p": {"id": 1}})
        first = await storage.get("k")
        first["p"]["id"] = 999  # mutate the returned dict
        assert (await storage.get("k"))["p"]["id"] == 1  # store unaffected
```

!!! note "Mark integration tests that need a real server"
    Tests against a live Redis/Postgres should be marked (e.g.
    `@pytest.mark.integration`) and skipped in the default run, so contributors
    without those services can still run the unit suite. The project uses
    `asyncio_mode="auto"`, so async tests are plain `async def` with no marker.

## See also

- [Storage strategies](../guide/storage.md) — when each strategy is used and how
  `MemoryStorage` behaves.
- [Encoding internals](encoding.md) — the `{h, p}` payload your backend stores
  and the dedup key it is stored under.
