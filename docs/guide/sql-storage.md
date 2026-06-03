# SQL Storage

[`SQLAlchemyStorage`][telegram_menu_builder.storage.sqlalchemy.SQLAlchemyStorage]
is a persistent, concurrency-safe [storage backend](storage.md) backed by a real
relational database. Where [`MemoryStorage`](storage.md#using-memorystorage)
loses every non-inline callback on restart and is single-threaded only, this
backend survives process restarts and is safe to share across concurrent async
tasks.

It is built on **SQLAlchemy 2.0 async (Core)** and a single implementation drives
three database families:

- **PostgreSQL / Supabase** (Supabase is just hosted Postgres)
- **MySQL / MariaDB**
- **SQLite**

Only the UPSERT statement is dialect-aware; everything else — the schema, TTL
handling, and queries — is shared. Reach for it when you need callbacks to outlive
a single process: multi-worker deployments, horizontally scaled bots, or anything
that must survive a redeploy.

!!! success "Verified against real databases"
    The full behavioral suite runs on SQLite and is verified end-to-end against
    **PostgreSQL 16** (via `asyncpg`) and **MariaDB 12.3.2** (via `aiomysql`). See the
    development guide's *Integration tests against real databases* section to reproduce it.

!!! note "When inline is enough"
    Small callbacks ride *inline* in the 64-byte `callback_data` and never touch
    storage at all — those survive restarts regardless of backend. A SQL backend
    only matters for the `Short`/`Persistent` payloads that spill to storage. See
    [Storage strategies](storage.md#strategy-selection) for the byte budget.

## Installation

The backend ships behind optional extras so the driver stack is opt-in. The base
`sql` extra installs SQLAlchemy plus `aiosqlite`, so **SQLite works out of the
box**. Add a driver extra for Postgres or MySQL.

| Database | Install | Driver | URL scheme |
| --- | --- | --- | --- |
| SQLite | `pip install "telegram-menu-builder[sql]"` | `aiosqlite` | `sqlite+aiosqlite://` |
| PostgreSQL / Supabase | `pip install "telegram-menu-builder[sql,postgres]"` | `asyncpg` | `postgresql+asyncpg://` |
| MySQL / MariaDB | `pip install "telegram-menu-builder[sql,mysql]"` | `asyncmy` | `mysql+asyncmy://` |

The `postgres` and `mysql` extras add only their async driver; SQLAlchemy itself
comes from `sql`, so always include `sql` alongside them. To pull in every
optional backend (Redis + SQL + both drivers) at once:

```bash
pip install "telegram-menu-builder[all]"
```

!!! note "MySQL driver: `asyncmy` or `aiomysql`"
    `[mysql]` installs `asyncmy`, a fast compiled driver. If it has no prebuilt wheel for
    your platform (building from source needs a C toolchain), install the pure-Python
    `aiomysql` instead and use the `mysql+aiomysql://` scheme — the backend behaves
    identically because both ride SQLAlchemy's MySQL dialect.

!!! note "Supabase"
    Supabase is plain PostgreSQL. Use its **Postgres connection string** with the
    `postgresql+asyncpg://` scheme and the `[postgres]` extra — there is nothing
    Supabase-specific to configure here.

    ```python
    storage = SQLAlchemyStorage(
        database_url="postgresql+asyncpg://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres"
    )
    ```

## Quick start

Three things matter: construct the backend with a `database_url`, call
`create_schema()` **once at startup** to create the table, and pass the **same
instance** to both `MenuBuilder` and `MenuRouter`.

```python
from telegram_menu_builder import MenuBuilder, MenuRouter
from telegram_menu_builder.storage import SQLAlchemyStorage

# One instance, shared by builder and router.
storage = SQLAlchemyStorage(database_url="sqlite+aiosqlite:///bot.db")


async def main() -> None:
    # Create the backing table once at startup. Idempotent — safe to call always.
    await storage.create_schema()

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
    `SQLAlchemyStorage` object to both — see
    [Storage](storage.md#storage) for the shared-instance pattern.

!!! warning "The table is not auto-created"
    Unlike `MemoryStorage`, this backend does **not** create its table lazily on
    first write. Call `await storage.create_schema()` once during startup before
    serving traffic, or every `set`/`get` will fail against a missing table.

## Bring your own engine

Instead of a URL you can hand the backend an existing
[`AsyncEngine`][sqlalchemy.ext.asyncio.AsyncEngine] — useful when your app already
manages a connection pool (e.g. shared with your ORM or web framework). Pass
exactly one of `database_url` or `engine`; supplying both or neither raises
`ValueError`.

```python
from sqlalchemy.ext.asyncio import create_async_engine

from telegram_menu_builder.storage import SQLAlchemyStorage

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/app")

storage = SQLAlchemyStorage(engine=engine)
await storage.create_schema()
```

!!! warning "A borrowed engine is not disposed"
    When you construct from `database_url`, the backend **owns** the engine and
    disposes it on [`close()`](#concurrency-and-lifecycle). When you pass `engine=`,
    the backend **borrows** it: `close()` leaves the engine intact so the rest of
    your application can keep using it. Dispose it yourself when your app shuts
    down.

## Schema and table

The backend stores everything in one table (default name `menu_callbacks`):

| Column | Type | Notes |
| --- | --- | --- |
| `key` | `VARCHAR(255)` | Primary key — the deterministic callback reference. |
| `value` | `JSON` | The `{"h": handler, "p": params}` payload. |
| `expires_at` | timezone-aware UTC datetime, indexed | `NULL` = never expires. |

Customise the table name or place it in a specific schema/namespace at
construction:

```python
storage = SQLAlchemyStorage(
    database_url="postgresql+asyncpg://user:pass@localhost/app",
    table_name="tg_menu_callbacks",
    schema="bot",
)
```

DDL is **explicit**, never implicit:

- `await storage.create_schema()` creates the table and its `expires_at` index.
  It is idempotent (`checkfirst=True`), so calling it on every startup is safe.
- `await storage.drop_schema()` drops the table (also idempotent).

!!! note "Plays well with managed migrations"
    Because the table is created by an explicit, idempotent call rather than
    magic-on-first-write, this backend fits **migration-managed** setups cleanly.
    On Supabase or an Alembic-managed database you can let your migration tool own
    the DDL and skip `create_schema()` entirely — just make sure the table matches
    the columns above. The names default to `menu_callbacks` with no schema.

## TTL and cleanup

The 64-byte encoder spills two kinds of payload to storage, and the TTL on each
follows directly from the strategy that produced it:

- **Short** callbacks are written with a TTL (`MenuAction.ttl`, default `3600`
  seconds). Their `expires_at` is set to now + ttl, and an expired row is treated
  as missing on read — `get`/`exists`/`keys` filter it out lazily.
- **Persistent** callbacks are written with no TTL, so `expires_at` is `NULL` and
  the row never expires.

Expired rows are filtered at query time but **not** deleted on read, so a busy bot
accumulates dead `Short` rows. Reclaim them with `cleanup_expired()`, which deletes
every elapsed row and returns how many it removed:

```python
removed = await storage.cleanup_expired()
logger.info("reclaimed %d expired callbacks", removed)
```

Run it periodically (e.g. from a `JobQueue` job or a cron task). For monitoring,
`get_stats()` returns a live snapshot:

```python
stats = await storage.get_stats()
# {
#     "total_keys": 128,
#     "keys_with_ttl": 96,    # Short callbacks
#     "expired_keys": 12,     # elapsed but not yet swept
#     "active_keys": 116,
# }
```

!!! note "`get_stats()` is async here"
    Unlike `MemoryStorage.get_stats()` (synchronous, reads an in-memory dict),
    `SQLAlchemyStorage.get_stats()` issues a database query and must be awaited.

## Concurrency and lifecycle

Unlike `MemoryStorage` — which is single-event-loop only and does no locking —
`SQLAlchemyStorage` is safe to share across **concurrent async tasks**. Each
operation runs in one short transaction over a pooled connection, and the database
provides the isolation. It also survives process restarts, since the data lives in
a real database rather than process memory.

The backend supports `close()` and the async context-manager protocol. Closing
disposes the engine **only if the backend owns it** (constructed from
`database_url`); a borrowed `engine=` is left untouched. After closing, any further
operation raises.

```python
async with SQLAlchemyStorage(database_url="sqlite+aiosqlite:///bot.db") as storage:
    await storage.create_schema()
    builder = MenuBuilder(storage=storage)
    router = MenuRouter(storage=storage)
    ...
# Owned engine disposed here.
```

!!! note "In-memory SQLite for tests"
    `sqlite+aiosqlite:///:memory:` is handy in tests — the backend configures a
    `StaticPool` automatically so the single in-memory connection persists across
    operations. Remember to `await create_schema()` after construction.

## Caveats

- **`keys()` uses SQL `LIKE`, not `fnmatch`.** The glob `pattern` is translated and
  pushed down to the database: `*` maps to `%` and `?` maps to `_`. It does **not**
  support `fnmatch`-style `[seq]` character classes the way `MemoryStorage.keys()`
  does. Stick to `*` and `?` for portable patterns.
- **Timezone handling is normalized to UTC.** `expires_at` is always stored and compared in
  UTC. PostgreSQL uses a real `TIMESTAMPTZ`; SQLite and MySQL/MariaDB have no true
  timezone-aware type, so the `UtcDateTime` decorator stores UTC and re-attaches UTC `tzinfo`
  on read — you never see naive datetimes, and TTL comparisons stay correct on every backend.
- **`get_stats()` is portable.** The expired-row count uses `SUM(CASE …)` rather than
  `COUNT(…) FILTER (…)`, which MySQL/MariaDB do not support, so the same query runs on every
  dialect.

## See also

- [Storage backends](storage.md) — the three-tier strategy and `MemoryStorage`.
- [Custom storage backends](../advanced/custom-storage.md) — the backend contract,
  plus Redis and hand-rolled `aiosqlite` sketches.
- [Storage API reference](../api/storage.md) — generated reference for the storage
  classes.
