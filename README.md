# Telegram Menu Builder

[![PyPI version](https://img.shields.io/pypi/v/telegram-menu-builder.svg)](https://pypi.org/project/telegram-menu-builder/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](docs/python-compatibility.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/smoxy/telegram-menu-builder/actions/workflows/ci.yml/badge.svg)](https://github.com/smoxy/telegram-menu-builder/actions/workflows/ci.yml)
[![Type checked: mypy + pyright](https://img.shields.io/badge/types-mypy%20%2B%20pyright-blue)](https://github.com/microsoft/pyright)
[![Linting: ruff](https://img.shields.io/badge/linting-ruff-red)](https://github.com/astral-sh/ruff)

A type-safe, async-first Python library for building recursive **inline keyboard menus** in
[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v20+. You declare
buttons with a fluent `MenuBuilder`, the library encodes each callback payload to fit Telegram's
64-byte limit (compressing inline or spilling to pluggable storage), and a `MenuRouter` decodes
incoming callbacks and dispatches them to your handlers.

📖 **Documentation:** <https://smoxy.github.io/telegram-menu-builder/> — or jump to the
[doc index below](#-documentation).

> **Status:** alpha (`0.x`). The API may change before `1.0`. See the [changelog](CHANGELOG.md).

## ✨ Features

- 🏗️ **Fluent builder API** — chainable, readable menu construction.
- 📦 **Smart callback encoding** — automatic inline / short-term / persistent strategy to stay
  under Telegram's 64-byte limit, with zlib compression and deduplication.
- 🧭 **Routing & middleware** — `MenuRouter` dispatches callbacks to named handlers with
  `before` / `after` / `on_error` hooks and handler groups.
- 🔄 **Unlimited nesting** — submenus and navigation (back / next / exit / cancel) buttons.
- 🧩 **Pluggable storage** — in-memory and built-in async SQL backends are included; implement the
  `StorageBackend` protocol (or subclass `BaseStorage`) for Redis and other custom backends.
- 🔐 **Strict typing** — full type hints, validated with both `mypy --strict` and `pyright`
  (Pydantic v2 models), shipped with `py.typed`.
- 🧪 **Well tested** — ~90% coverage, CI on every push and pull request.

## 🚀 Quick start

```bash
pip install telegram-menu-builder
```

Optional extras: `telegram-menu-builder[redis]`, `[sql]` (plus `[postgres]` / `[mysql]` drivers),
`[dev]`, `[docs]`. See [Installation](docs/installation.md).

```python
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from telegram_menu_builder import MenuBuilder, MenuRouter

router = MenuRouter()


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    menu = (
        MenuBuilder()
        .add_item("🌍 Language", handler="set_language")
        .add_item("👤 Profile", handler="edit_profile", user_id=update.effective_user.id)
        .columns(2)
        .add_back_button()
        .build()
    )
    await update.message.reply_text("⚙️ Settings", reply_markup=menu)


@router.handler("set_language")
async def handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict) -> None:
    # `params` are the values you passed to add_item(...), decoded from the callback.
    await update.callback_query.edit_message_text("Choose a language…")


app = Application.builder().token("YOUR_TOKEN").build()
app.add_handler(CallbackQueryHandler(router.route))
app.run_polling()
```

> **Tip:** in `async` code, prefer `await builder.build_async()`. `build()` is a synchronous
> convenience wrapper (it also works inside a running event loop). See
> [Building menus](docs/guide/menu-building.md#build-vs-build_async).

## 📚 Examples at a glance

**Buttons carry arbitrary parameters** — they are encoded into the callback and decoded back into
the `params` dict your handler receives:

```python
menu = (
    MenuBuilder()
    .add_item("📝 Edit", handler="edit_user", user_id=123, field="email")
    .add_item("🗑️ Delete", handler="delete_user", user_id=123, confirm=True)
    .columns(1)
    .add_back_button(handler="user_list", page=2)
    .build()
)
```

**Nested submenus:**

```python
users = MenuBuilder().add_item("Add user", handler="add_user").add_back_button()
main = MenuBuilder().add_submenu("👥 Users", users)
```

**Bring your own storage** — in-memory and SQL backends ship built-in; for anything else (e.g.
Redis) subclass `BaseStorage` (or satisfy the `StorageBackend` protocol) and pass it in:

```python
from telegram_menu_builder import MenuBuilder

builder = MenuBuilder(storage=my_redis_storage)  # full guide: docs/advanced/custom-storage.md
```

See the runnable [examples/](examples/) and the [guides](#-documentation) for complete,
copy-pasteable bots — including [ConversationHandler integration](docs/conversation_handler_guide.md).

## 🧠 How callback encoding works

Telegram limits `callback_data` to 64 bytes. The library chooses a strategy automatically:

1. **Inline** (fits in 64 bytes) — JSON → zlib → base64 directly in the callback.
2. **Short-term** — stored in the backend with a TTL; the callback carries a short reference.
3. **Persistent** — stored without expiry for large/long-lived payloads.

Identical payloads reuse the same key (deduplication). Full details:
[Callback encoding internals](docs/advanced/encoding.md).

## 📖 Documentation

📚 **Rendered site:** <https://smoxy.github.io/telegram-menu-builder/>

| Get started | Guides | Advanced | Reference |
| --- | --- | --- | --- |
| [Installation](docs/installation.md) | [Building menus](docs/guide/menu-building.md) | [Encoding internals](docs/advanced/encoding.md) | [MenuBuilder](docs/api/builder.md) |
| [Quick start](docs/quickstart.md) | [Routing callbacks](docs/guide/routing.md) | [Custom storage](docs/advanced/custom-storage.md) | [MenuRouter](docs/api/router.md) |
| | [Storage backends](docs/guide/storage.md) | | [Types & models](docs/api/types.md) |
| | [ConversationHandler](docs/conversation_handler_guide.md) | | [Encoding](docs/api/encoding.md) · [Storage](docs/api/storage.md) |

**Project docs:** [Changelog](CHANGELOG.md) · [Security policy](SECURITY.md) ·
[Dependency & CVE audit](docs/dependency-audit.md) · [Python compatibility](docs/python-compatibility.md) ·
[Development guide](docs/development.md) · [Contributing](CONTRIBUTING.md)

## 🤝 Contributing

**Every contribution is welcome** — bug reports, documentation, examples, and code alike. Start
with the [Contributing guide](CONTRIBUTING.md) and the [Development guide](docs/development.md).

```bash
git clone https://github.com/smoxy/telegram-menu-builder.git
cd telegram-menu-builder
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
make test          # run the suite (≈90% coverage)
```

Before opening a pull request, make sure the gates pass:

```bash
make lint          # ruff + black --check
make type-check    # mypy --strict + pyright
make test          # pytest with coverage
```

- 🐛 **Bugs** → [open an issue](https://github.com/smoxy/telegram-menu-builder/issues) (templates provided).
- 💡 **Ideas / questions** → [GitHub Discussions](https://github.com/smoxy/telegram-menu-builder/discussions).
- 🤖 **AI-assisted development** → this repo ships [`CLAUDE.md`](CLAUDE.md), [`AGENTS.md`](AGENTS.md),
  and ready-made agents/skills under [`.claude/`](.claude/) to keep changes consistent.

Releases are published to PyPI automatically via [GitHub Releases and trusted publishing](.github/workflows/python-publish.yml) — no manual token handling needed.

## 🔐 Security

Found a vulnerability? Please report it privately — see [SECURITY.md](SECURITY.md). Dependency CVEs
are tracked in the [dependency audit](docs/dependency-audit.md) (for example, pydantic is pinned
`>=2.4` to exclude CVE-2024-3772).

## 🗺️ Roadmap

- ✅ Fluent builder, navigation, submenus
- ✅ Smart callback encoding (inline / short-term / persistent) with compression & dedup
- ✅ `MenuRouter` with middleware and handler groups
- ✅ In-memory storage backend, strict typing, CI
- ✅ Built-in SQL backend via SQLAlchemy (async) for PostgreSQL/Supabase, MySQL/MariaDB, and SQLite
  (install `[sql]`, plus `[postgres]` or `[mysql]` for those drivers — see
  [storage backends](docs/guide/storage.md))
- 🚧 Built-in Redis backend (the `[redis]` extra is reserved; bring-your-own works today — see
  [custom storage](docs/advanced/custom-storage.md))
- 📅 Helpers for pagination and form/wizard flows

## 📝 License

Released under the **MIT License** — see [LICENSE](LICENSE). Free for commercial, private, and
personal use, modification, and distribution. Using this code to **train AI/ML models is explicitly
permitted**. Attribution is appreciated but not required.

---

Made with ❤️ for the Telegram Bot community · [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v20+ · [Pydantic v2](https://github.com/pydantic/pydantic)
