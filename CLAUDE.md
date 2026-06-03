# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

`telegram-menu-builder` is a fluent builder for recursive inline-keyboard menus on
top of [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot).
You declare buttons with a chainable `MenuBuilder` API, the library encodes the
callback payload to fit Telegram's 64-byte limit (compressing inline or spilling to a
pluggable storage backend), and a `MenuRouter` decodes incoming callback queries and
dispatches them to your registered handlers. It is a published PyPI package, MIT
licensed, alpha status, Python 3.12-only, with strict typing and Pydantic v2 models.

## Architecture map

| Module | Responsibility |
| --- | --- |
| `src/telegram_menu_builder/types.py` | Pydantic v2 models, enums, exceptions. `StorageStrategy(StrEnum)` = INLINE/SHORT/PERSISTENT. `MenuAction(handler, params, strategy, ttl)`. `MenuItem(text, callback_data<=64 bytes, url)` (frozen, `to_telegram_button()`). `LayoutConfig(columns 1-8, max_rows)`. `NavigationButton`, `NavigationConfig` (exit XOR cancel). `CallbackData`. Exceptions: `MenuBuilderError` -> `EncodingError`, `DecodingError`, `StorageError`, `ValidationError`. |
| `src/telegram_menu_builder/builder.py` | `MenuBuilder` fluent API: `add_item`, `add_items`, `add_url_button`, `add_submenu`, `get_submenu`, `columns`, `max_rows`, `add_back/next/exit/cancel_button`, `build()`, `build_async()`. `add_*` methods store pending specs; encoding is deferred to `build_async()`. |
| `src/telegram_menu_builder/router.py` | `MenuRouter`: `handler(name)` decorator, `register_handler(s)`, `unregister_handler`, `set_default_handler`, `route(update, context)`, `before`/`after`/`on_error` middleware, `get_handler`/`list_handlers`, `storage`/`encoder` properties, `auto_answer`. `RouterGroup(prefix, router)` for `"prefix.name"` handlers. |
| `src/telegram_menu_builder/encoding.py` | `CallbackEncoder`: 3-tier size strategy (INLINE/SHORT/PERSISTENT), deterministic 12-char MD5 dedup key (`usedforsecurity=False`), `encode`/`decode`, `estimate_encoded_size(action)`, `cleanup_callback()`. |
| `src/telegram_menu_builder/storage/base.py` | `StorageBackend` Protocol (`runtime_checkable`) + `BaseStorage` ABC (`close`/`is_closed`/`_ensure_open`, async context manager). Methods: `set`/`get`/`delete`/`exists`/`clear`/`keys(pattern)`. |
| `src/telegram_menu_builder/storage/memory.py` | `MemoryStorage(BaseStorage)`: TTL expiry, defensive copies, `cleanup_expired()`, `get_stats()`. Not thread-safe (single-threaded async use). |
| `src/telegram_menu_builder/storage/sqlalchemy.py` | `SQLAlchemyStorage(BaseStorage)`: async SQLAlchemy 2.0 **Core** backend for PostgreSQL/Supabase, MySQL/MariaDB, SQLite from one code path. Dialect-branched UPSERT (pg/sqlite `on_conflict`, mysql/mariadb `on_duplicate_key`, delete-then-insert fallback), `UtcDateTime` TypeDecorator, `StaticPool` for `:memory:`, owns-vs-borrows engine, explicit `create_schema()`/`drop_schema()` (no implicit DDL), `cleanup_expired()`, **async** `get_stats()` (portable `SUM(CASE)`). Lazily exported via module `__getattr__` so importing the package never imports SQLAlchemy. Pool-safe for concurrent tasks. |

## Build / test / lint commands

Prefer the `make` targets; raw equivalents are listed for ad-hoc runs.

| Task | Make target | Raw command |
| --- | --- | --- |
| Install dev env | `make install-dev` | `pip install -e ".[dev]"` (+ `pre-commit install`) |
| Run tests | `make test` | `pytest` |
| Tests + coverage | `make test-cov` | `pytest --cov --cov-report=html --cov-report=term` |
| Lint | `make lint` | `ruff check src tests` |
| Format | `make format` | `black src tests` then `ruff check --fix src tests` |
| Type check | `make type-check` | `mypy src` and `pyright` (i.e. `pyright src`) |
| Pre-commit hooks | `make pre-commit` | `pre-commit run --all-files` |
| Build dist | `make build` | `python -m build` |
| Docs | `make docs` | `mkdocs build` (site config in `mkdocs.yml`) |
| Dependency audit | `make audit` | `pip-audit` (upgrade pip first) |

Both `mypy` and `pyright` MUST pass on `src/` before any change is considered done.

## Conventions

- Strict `mypy` (`strict = true`) and strict `pyright` (`typeCheckingMode = "strict"`)
  must both pass on `src/`. Do not introduce `# type: ignore` or leaking `Any`.
- Google-style docstrings on all public APIs.
- 100-char line length (`E501` is delegated to black, but keep lines wrapped).
- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `ci:`, `test:`, ...).
- Builder mutator methods return `Self` so calls chain fluently.
- Double quotes; ruff rule families `E,W,F,I,N,UP,B,C4,DTZ,T10,ISC,ICN,PIE,PT,Q,RSE,RET,SIM,TID,ARG,ERA,PL,RUF` (ignores `E501`, `PLR0913`, `PLR2004`).
- Tests are class-based with `@pytest.fixture` methods; `asyncio_mode = "auto"`, so
  async tests are plain `async def` with NO `@pytest.mark.asyncio` marker.

## How callback encoding works

1. A `MenuAction` becomes a compact dict `{"h": handler, "p": params}`.
2. The encoder tries INLINE first: JSON -> zlib (level 9) -> base64, kept only if the
   result fits 64 bytes. Prefix is `I:` (uncompressed) or `IC:` (compressed).
3. If it does not fit, the dict is stored under a deterministic 12-char MD5 key and the
   callback carries a reference: `S:<key>` (SHORT, with TTL) when JSON < 500 bytes, or
   `P:<key>` (PERSISTENT, no expiry) when larger.
4. Decoding dispatches on the prefix: `I:`/`IC:` decode inline; `S:`/`P:` look the key
   up in storage (a missing key raises `DecodingError`).
5. The MD5 key is a non-cryptographic dedup key only (`hashlib.md5(..., usedforsecurity=False)`).

## The async gotcha

`add_*` methods only record pending specs — no callback data is encoded until build time.
Encoding is deferred to `build_async()` so it always runs inside an async context.

- `build_async()` is the real builder; prefer `await build_async()` in async code.
- `build()` is a SYNC convenience wrapper: with no running loop it calls
  `asyncio.run(build_async())`; inside a running loop it runs `build_async()` on a
  short-lived worker thread. Avoid `build()` inside async handlers.

## Version sources

- `pyproject.toml` `[project].version` is the single source of truth.
- `src/telegram_menu_builder/__init__.py` reads `__version__` via
  `importlib.metadata.version("telegram-menu-builder")` — never hardcode a version there.
- `CHANGELOG.md` (Keep a Changelog format) must be kept in sync with every release;
  land user-facing changes under `## [Unreleased]` as you go.

## Dependency / Python policy

- python-telegram-bot: `>=20.0,<22.8`.
- pydantic: `>=2.4,<3.0` (floor raised to 2.4 to exclude CVE-2024-3772; the library
  does not use `EmailStr`, so it was never exploitable — defense in depth).
- Optional storage extras: `[sql]` = `sqlalchemy[asyncio]>=2.0.30,<3.0` + `aiosqlite`;
  `[postgres]` = `asyncpg`; `[mysql]` = `asyncmy` (the pure-Python `aiomysql` also works —
  same SQLAlchemy MySQL dialect, useful where `asyncmy` lacks a wheel). `[redis]` is reserved
  (bring-your-own today). `SQLAlchemyStorage` is verified against PostgreSQL 16 and MariaDB 12.3.2.
- Python: 3.12-only (`requires-python = ">=3.12"`). This is deliberate; do not widen it
  in normal docs. See `docs/dependency-audit.md` and `docs/python-compatibility.md` for
  the audit and the compatibility/feasibility analysis.

## Do-not list

- Do not relax type-checker strictness (`mypy strict`, `pyright strict`) or add blanket
  `# type: ignore` / `Any` to silence errors.
- Do not bump the version without updating `CHANGELOG.md`.
- Do not edit the generated `site/` directory (mkdocs output).
