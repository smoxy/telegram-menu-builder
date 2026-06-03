---
name: add-storage-backend
description: Scaffold a new StorageBackend (e.g. Redis, SQL) implementing the Protocol plus matching tests. Use when the user says "add a storage backend", "implement Redis storage", or "implement SQL storage".
---

# Add a storage backend

Scaffold a new storage backend for `telegram-menu-builder` that satisfies the
`StorageBackend` protocol, with matching tests and docs.

## Reference

Read `src/telegram_menu_builder/storage/base.py` (the `StorageBackend` Protocol and the
`BaseStorage` ABC) and `src/telegram_menu_builder/storage/memory.py` (the reference
implementation) before writing anything. New backends subclass `BaseStorage`.

## Steps

1. **Create `src/telegram_menu_builder/storage/<name>.py`** with a class
   `class <Name>Storage(BaseStorage):` implementing all abstract methods —
   `set(key, data, ttl=None)`, `get(key)`, `delete(key)`, `exists(key)`, `clear()`,
   `keys(pattern=None)` — and overriding `close()` to release connections/resources.
   - Call `self._ensure_open()` at the top of each operation.
   - Match the type signatures from the protocol exactly (`dict[str, Any]`,
     `int | None`, `bool`, `list[str]`). Keep `mypy strict` + `pyright strict` clean.
   - Google-style docstrings, 100-char lines.
2. **Keep the backend module's imports normal.** Import the third-party package
   (`sqlalchemy`, `aiosqlite`, `redis.asyncio`, …) at module top level — this keeps strict
   typing clean (no `Any` leaking from guarded fallbacks). The module is only ever imported
   through the lazy export in step 3, so a missing dependency never breaks
   `import telegram_menu_builder`.

   The extras already exist in `pyproject.toml`: `[redis]` (`redis>=5.0`), `[sql]`
   (`sqlalchemy[asyncio]>=2.0.30,<3.0`, `aiosqlite>=0.19`), `[postgres]` (`asyncpg>=0.29`),
   and `[mysql]` (`asyncmy>=0.2.9`).
3. **Export it lazily (PEP 562).** In both `src/telegram_menu_builder/storage/__init__.py`
   and the package `src/telegram_menu_builder/__init__.py`: list the class in `__all__` (kept
   sorted), import it under `if TYPE_CHECKING:` for the type checkers, and resolve the real
   import inside a module `__getattr__` that raises a clear `ImportError` pointing at the
   matching extra when the dependency is absent, e.g.:

   ```python
   def __getattr__(name: str) -> Any:
       if name == "RedisStorage":
           try:
               from telegram_menu_builder.storage.redis import RedisStorage
           except ImportError as exc:  # pragma: no cover
               raise ImportError(
                   "RedisStorage requires the 'redis' extra: pip install 'telegram-menu-builder[redis]'"
               ) from exc
           return RedisStorage
       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
   ```

   This way `import telegram_menu_builder` never imports the optional dependency. See
   `SQLAlchemyStorage` for the reference implementation.
4. **Add tests** `tests/test_<name>_storage.py` mirroring `tests/test_storage.py`
   (set/get/delete/exists/clear/keys, TTL expiry, defensive copies). Use an in-memory
   fixture for the dependency — `fakeredis` for Redis, an in-memory SQLite URL
   (`sqlite+aiosqlite:///:memory:`) for SQL. Mark backend tests that need the real
   service or a running container with `@pytest.mark.integration`. Class-based,
   `@pytest.fixture` methods, plain `async def` (no asyncio marker).
5. **Update docs**: `docs/guide/storage.md` and `docs/advanced/custom-storage.md`, and
   add an entry under `## [Unreleased]` in `CHANGELOG.md` (`### Added`).
6. **Verify**: `make type-check && make test` (and `make lint`). Both type checkers must
   pass on `src/`.

## Output

List the files created/edited and the resulting test/coverage status.
