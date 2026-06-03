# Storage

Telegram limits `callback_data` to 64 bytes. Many real-world menus carry more
state than that, so the library encodes callbacks with a three-tier strategy:
small payloads ride inline in the callback data itself, while larger payloads
are stored in a backend and referenced by a short key. A
[`StorageBackend`][telegram_menu_builder.StorageBackend] holds those non-inline
payloads.

Both [`MenuBuilder`](menu-building.md) and [`MenuRouter`](routing.md) default to
an in-process [`MemoryStorage`][telegram_menu_builder.MemoryStorage] if you do
not provide one.

!!! warning "Builder and router must share a backend"
    The builder *writes* non-inline payloads to storage and the router *reads*
    them back. If they use different backends, large callbacks encode fine but
    fail to decode (you will see `DecodingError: Callback data expired or not
    found`). Always pass the **same** storage instance to both.

    ```python
    from telegram_menu_builder import MenuBuilder, MenuRouter
    from telegram_menu_builder.storage import MemoryStorage

    storage = MemoryStorage()
    builder = MenuBuilder(storage=storage)
    router = MenuRouter(storage=storage)
    ```

## Strategy selection

The encoder picks a strategy automatically based on the encoded payload size.
You never select it manually in normal use.

| Strategy | Payload size | Stored? | TTL | Prefix |
| --- | --- | --- | --- | --- |
| Inline (raw) | < 60 bytes | No — lives in `callback_data` | n/a | `I:` |
| Inline (compressed) | < 60 bytes after zlib | No — lives in `callback_data` | n/a | `IC:` |
| Short | 60–500 bytes | Yes | `MenuAction.ttl` (default 3600s) | `S:` |
| Persistent | > 500 bytes | Yes | none (never expires) | `P:` |

- **Inline** keeps the whole payload in the callback data, base64-encoded, using
  whichever is smaller of the raw JSON or its zlib-compressed form. Compressed
  payloads carry the `IC:` prefix; uncompressed ones use `I:`.
- **Short** stores the payload under a deterministic key with a time-to-live and
  references it as `S:<key>`. The TTL comes from `MenuAction.ttl` (default
  `3600`, clamped to 60–86400 seconds). These entries expire, so a stale button
  decodes to a `DecodingError` — handle that with
  [`on_error` middleware](routing.md#middleware).
- **Persistent** stores the payload with no expiry and references it as
  `P:<key>`. Use this sparingly; entries are never reclaimed automatically.

!!! note "Prefer compact params"
    Keeping callbacks inline avoids any storage round-trip and survives bot
    restarts with `MemoryStorage`. Short integer ids and short string keys
    usually stay inline; large breadcrumbs and nested metadata push you into
    short/persistent storage. See [Encoding internals](../advanced/encoding.md)
    for the byte budget.

## Using MemoryStorage

`MemoryStorage` keeps everything in Python dictionaries with TTL-based
expiration. It is the default backend and is ideal for development, tests, and
single-process bots.

```python
from telegram_menu_builder.storage import MemoryStorage

storage = MemoryStorage()
await storage.set("abc123", {"h": "edit", "p": {"id": 1}}, ttl=600)
data = await storage.get("abc123")   # -> {'h': 'edit', 'p': {'id': 1}}
```

It implements the full backend contract (`set`, `get`, `delete`, `exists`,
`clear`, `keys`, `close`) plus two helpers:

### `cleanup_expired()`

Expired entries are removed lazily on access, but in a long-running bot you may
want to reclaim memory proactively. `cleanup_expired()` sweeps all expired keys
and returns how many it removed:

```python
removed = await storage.cleanup_expired()
logger.info("reclaimed %d expired callbacks", removed)
```

### `get_stats()`

`get_stats()` returns a snapshot useful for monitoring:

```python
stats = storage.get_stats()
# {
#     "total_keys": 42,
#     "keys_with_ttl": 30,
#     "expired_keys": 3,    # expired but not yet swept
#     "active_keys": 39,
# }
```

!!! warning "MemoryStorage is not thread-safe"
    `MemoryStorage` is designed for single-threaded async use (one event loop).
    It performs no locking. Do not share one instance across threads or
    processes; for those scenarios use a custom backend such as Redis or SQL.
    Data is also lost on process restart — `Short`/`Persistent` callbacks
    created before a restart will fail to decode afterwards.

## Lifecycle

`MemoryStorage` (and any `BaseStorage` subclass) supports `close()` and the
async context-manager protocol. After closing, the backend raises if used again.

```python
async with MemoryStorage() as storage:
    builder = MenuBuilder(storage=storage)
    ...
# storage is closed here
```

## Other backends

### SQL (available)

A production-ready async SQL backend ships as
[`SQLAlchemyStorage`][telegram_menu_builder.storage.sqlalchemy.SQLAlchemyStorage].
It persists callbacks in a relational database via SQLAlchemy 2.0 async (Core)
and works across PostgreSQL/Supabase, MySQL/MariaDB, and SQLite from a single
implementation. Unlike `MemoryStorage`, it is safe for concurrent async tasks
and survives process restarts. Install the `[sql]` extra (which bundles
SQLAlchemy + `aiosqlite`), plus the matching driver for your database
(`[postgres]` for PostgreSQL/Supabase, `[mysql]` for MySQL/MariaDB):

```python
from telegram_menu_builder.storage import SQLAlchemyStorage

storage = SQLAlchemyStorage(database_url="sqlite+aiosqlite:///callbacks.db")
await storage.create_schema()  # once at startup; idempotent
```

See the [SQL storage guide](sql-storage.md) for database URLs, schema setup,
engine ownership, TTL cleanup, and monitoring.

### Redis (planned / bring-your-own)

A Redis backend is a **planned optional extra** (`pip install
"telegram-menu-builder[redis]"`) and is not bundled yet. Until it ships — or
whenever you need a backend the library doesn't provide — you can plug in your
own. See [Custom storage backends](../advanced/custom-storage.md) for the full
contract plus a Redis sketch.

## See also

- [Encoding internals](../advanced/encoding.md) — how the byte budget and
  prefixes are computed.
- [Custom storage backends](../advanced/custom-storage.md) — implement Redis,
  SQL, or anything else.
- [Routing callbacks](routing.md) — where decode failures from expired short
  entries surface.
