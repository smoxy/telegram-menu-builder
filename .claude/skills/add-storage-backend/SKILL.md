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
2. **Lazy / guarded import of the optional dependency.** Import the third-party package
   (e.g. `redis.asyncio`, `sqlalchemy`/`aiosqlite`) inside the module or `__init__`
   behind a `try/except ImportError`, and raise a clear `ImportError` that points the
   user at the matching extra, e.g.:

   ```python
   try:
       import redis.asyncio as redis
   except ImportError as exc:  # pragma: no cover
       raise ImportError(
           "RedisStorage requires the 'redis' extra: pip install 'telegram-menu-builder[redis]'"
       ) from exc
   ```

   The extras already exist in `pyproject.toml`: `[redis]` (`redis>=5.0`) and `[sql]`
   (`sqlalchemy>=2.0`, `aiosqlite>=0.19`).
3. **Export it.** Add the class to `src/telegram_menu_builder/storage/__init__.py`
   (`from ... import <Name>Storage` and its `__all__`) and to the package
   `src/telegram_menu_builder/__init__.py` `__all__` — keep both `__all__` lists sorted.
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
