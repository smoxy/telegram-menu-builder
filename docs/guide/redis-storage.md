# Redis / Valkey Storage

[`RedisStorage`][telegram_menu_builder.storage.redis.RedisStorage] is a
persistent, concurrency-safe [storage backend](storage.md) backed by Redis — or
its drop-in fork **Valkey**. Where [`MemoryStorage`](storage.md#using-memorystorage)
loses every non-inline callback on restart and is single-threaded only, this
backend survives process restarts and is safe to share across concurrent async
tasks (redis-py manages a connection pool for you).

A single class drives both servers. Valkey speaks the same RESP wire protocol as
Redis, so you point a normal `redis://` (or `rediss://` for TLS) URL at whichever
server you run — there is no separate client, dependency, or `ValkeyStorage`
class to learn.

The big practical difference from the [SQL backend](sql-storage.md): TTL is
**native**. Redis/Valkey expire short callbacks for you (the backend issues
`SET ... EX`), so there is **no `create_schema()` to call** and **no manual
cleanup** to schedule. Reach for it when you want a fast, in-memory-class data
store that still outlives a single process: multi-worker deployments,
horizontally scaled bots, or anything that must survive a redeploy.

!!! tip "We recommend Valkey"
    This project recommends **[Valkey](https://valkey.io/)** — the BSD-licensed,
    community-governed, RESP-compatible fork of Redis. It is a drop-in
    replacement: the same `redis://` URL and the same `[redis]` extra work
    unchanged, with no code differences on our side. See
    [what Valkey 9.1 delivers in security, performance, and more](https://valkey.io/blog/valkey-9-1-delivers-improvements-in-security-performance-and-more/)
    for why it is worth the switch.

!!! note "When inline is enough"
    Small callbacks ride *inline* in the 64-byte `callback_data` and never touch
    storage at all — those survive restarts regardless of backend. A Redis
    backend only matters for the `Short`/`Persistent` payloads that spill to
    storage. See [Storage strategies](storage.md#strategy-selection) for the byte
    budget.

## Installation

The backend ships behind the optional `[redis]` extra, which bundles the
[redis-py](https://github.com/redis/redis-py) async client (`redis>=5.0`). That
**one client serves both Redis and Valkey** — Valkey needs nothing extra.

```bash
pip install "telegram-menu-builder[redis]"
```

To pull in every optional backend (Redis + SQL + both SQL drivers) at once:

```bash
pip install "telegram-menu-builder[all]"
```

## Quick start

Two things matter: construct the backend with a `url`, and pass the **same
instance** to both `MenuBuilder` and `MenuRouter`. Unlike the SQL backend, there
is **no `await create_schema()`** step — the server manages its own keyspace and
expiry.

```python
from telegram_menu_builder import MenuBuilder, MenuRouter
from telegram_menu_builder.storage import RedisStorage

# One instance, shared by builder and router.
# The same redis:// URL points at a Redis OR a Valkey server.
storage = RedisStorage(url="redis://localhost:6379/0")


async def main() -> None:
    builder = MenuBuilder(storage=storage)
    router = MenuRouter(storage=storage)

    menu = await (
        builder
        .add_item("Settings", handler="open_settings", section="general")
        .add_item("Profile", handler="open_profile")
        .build_async()
    )
    # ... register handlers on `router`, then await router.route(update, context) ...
```

!!! warning "Builder and router must share one backend"
    The builder *writes* non-inline payloads and the router *reads* them back. If
    they hold different instances, large callbacks encode fine but decode to
    `DecodingError: Callback data expired or not found`. Always pass the same
    `RedisStorage` object to both — see
    [Storage](storage.md#storage) for the shared-instance pattern.

!!! note "No schema, no setup call"
    There is intentionally no `create_schema()` here. Where
    `SQLAlchemyStorage` needs an explicit table-creation step, Redis/Valkey
    create keys on first write and expire them on their own. Construct the
    backend and start serving.

## Connecting to Valkey

Because Valkey is wire-compatible with Redis, connecting to it is identical to
connecting to Redis: use a `redis://` URL pointing at your Valkey host.

```python
# A Valkey server — same scheme, same client, same extra.
storage = RedisStorage(url="redis://valkey.internal:6379/0")
```

For an encrypted connection (TLS), use the `rediss://` scheme — it works against
either server:

```python
storage = RedisStorage(url="rediss://valkey.internal:6379/0")
```

## Bring your own client

Instead of a URL you can hand the backend an existing async client — useful when
your app already manages a connection pool, or when you want to use a
`valkey.asyncio` client explicitly. Pass exactly one of `url` or `client`;
supplying both or neither raises `ValueError`.

```python
from redis.asyncio import Redis

from telegram_menu_builder.storage import RedisStorage

client = Redis.from_url("redis://localhost:6379/0")
storage = RedisStorage(client=client)
```

The `client` argument is **duck-typed**: any async client that speaks redis-py's
API works, including a [`valkey.asyncio`](https://github.com/valkey-io/valkey-py)
client. Configure the connection pool, RESP3, TLS, timeouts, and auth on **your**
client — the backend only issues `GET`/`SET`/`DELETE`/`EXISTS`/`SCAN` against it.

```python
from valkey.asyncio import Valkey

client = Valkey.from_url("valkey://localhost:6379/0", protocol=3)
storage = RedisStorage(client=client)
```

!!! warning "A borrowed client is not closed"
    When you construct from `url`, the backend **owns** the client and closes it
    (`aclose()`) on [`close()`](#lifecycle). When you pass `client=`, the backend
    **borrows** it: `close()` leaves the client open so the rest of your
    application can keep using it. Close it yourself when your app shuts down.

## Namespace

Every key the backend writes is prefixed with a `namespace` (default `"tmb:"`).
The prefix is invisible to callers — keys go in and come back without it — but it
means multiple stores can safely share one server or logical database. Both
`clear()` and `keys()` are **scoped to the namespace**, so they never touch
another app's data:

```python
storage = RedisStorage(url="redis://localhost:6379/0", namespace="mybot:")
```

!!! tip "Isolation, not FLUSHDB"
    `clear()` removes only this store's namespaced keys — it walks them with a
    namespace-scoped `SCAN MATCH` and `DELETE`s them, and **never** issues
    `FLUSHDB`. Anything stored under a different namespace on the same database is
    left untouched, so co-tenanting is safe.

## TTL

The 64-byte encoder spills two kinds of payload to storage, and the TTL on each
maps directly onto a Redis/Valkey key expiry:

- **Short** callbacks are written with a TTL (`MenuAction.ttl`, default `3600`
  seconds) via `SET ... EX`. The **server** enforces the expiry and removes the
  key when it elapses.
- **Persistent** callbacks are written with no TTL, so the key never expires.

Because expiry is server-enforced, an elapsed `Short` key is simply gone:
`get`/`exists` return `None`/`False` and `keys` does not list it. There is
**nothing to sweep**.

!!! note "No `cleanup_expired()` / `get_stats()` here"
    Unlike `MemoryStorage` and `SQLAlchemyStorage`, this backend exposes no
    `cleanup_expired()` or `get_stats()` helpers — the server reclaims expired
    keys natively. For introspection, reach for the live client via the
    [`client`][telegram_menu_builder.storage.redis.RedisStorage.client] property
    and use server commands directly, e.g. `await storage.client.dbsize()` or
    `await storage.client.info()`.

## Lifecycle

`RedisStorage` is safe to share across **concurrent async tasks** — redis-py
serves operations from a connection pool, and the server provides isolation. It
also survives process restarts, since the data lives in Redis/Valkey rather than
process memory.

The backend supports `close()` and the async context-manager protocol. Closing
calls `aclose()` on the client **only if the backend owns it** (constructed from
`url`); a borrowed `client=` is left untouched. After closing, any further
operation raises.

```python
async with RedisStorage(url="redis://localhost:6379/0") as storage:
    builder = MenuBuilder(storage=storage)
    router = MenuRouter(storage=storage)
    ...
# Owned client closed here.
```

## Caveats

- **`keys()` uses server-side `SCAN MATCH`, not `fnmatch`.** The glob `pattern`
  is pushed down to the server, which supports `*` and `?` like
  `MemoryStorage.keys()` — but its character-class **negation differs**:
  Redis/Valkey write it `[^abc]`, whereas Python's `fnmatch` (used by
  `MemoryStorage`) writes `[!abc]`. Stick to `*` and `?` for portable patterns,
  and remember the `[^...]` form if you negate a class against this backend.
- **`clear()` is namespace-scoped, never `FLUSHDB`.** See
  [Namespace](#namespace) — it only removes this store's keys, so it is safe on a
  shared database.

!!! success "Verified against fakeredis and live servers"
    The behavioral suite runs against
    [`fakeredis`](https://github.com/cunla/fakeredis-py) in the default test run,
    and is verified end-to-end against **live Redis 7.4.9 and Valkey 8.1.8**
    (including real, server-enforced TTL expiry) via the integration suite when
    `TMB_TEST_REDIS_URL` / `TMB_TEST_VALKEY_URL` point at a reachable server. See
    the Docker recipe below to reproduce it.

### Throwaway server with Docker

You can run a server and the test client as containers on a private network — no
host install or published port required. The same suite runs against either
image:

```bash
docker network create tmb-net

# --- Valkey (recommended) ---
docker run -d --name tmb-valkey --network tmb-net valkey/valkey:8
docker run --rm --network tmb-net -v "$PWD:/app" -w /app \
  -e TMB_TEST_VALKEY_URL="redis://tmb-valkey:6379/0" python:3.12-slim \
  sh -lc "pip install -e '.[redis]' pytest pytest-asyncio pytest-cov pytest-mock && pytest tests/test_redis_storage.py"

# --- Redis ---
docker run -d --name tmb-redis --network tmb-net redis:7-alpine
docker run --rm --network tmb-net -v "$PWD:/app" -w /app \
  -e TMB_TEST_REDIS_URL="redis://tmb-redis:6379/0" python:3.12-slim \
  sh -lc "pip install -e '.[redis]' pytest pytest-asyncio pytest-cov pytest-mock && pytest tests/test_redis_storage.py"

docker rm -f tmb-valkey tmb-redis && docker network rm tmb-net
```

## See also

- [Storage backends](storage.md) — the three-tier strategy and `MemoryStorage`.
- [Custom storage backends](../advanced/custom-storage.md) — the backend
  contract, plus Redis and hand-rolled `aiosqlite` sketches.
- [Storage API reference](../api/storage.md) — generated reference for the
  storage classes.
