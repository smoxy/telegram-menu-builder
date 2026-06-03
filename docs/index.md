# Telegram Menu Builder

A powerful, type-safe Python library for creating recursive inline keyboard menus in
[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v20+.

!!! warning "Alpha status"
    This project is currently in **alpha**. The public API may change before the `1.0.0`
    release. Pin a version in production and review the [Changelog](changelog.md) before
    upgrading.

## Features

- **Builder Pattern API** &mdash; intuitive, fluent interface for menu construction.
- **Type-Safe** &mdash; full type hints for Python 3.12+, validated with both mypy and Pyright in strict mode.
- **Smart Callback Encoding** &mdash; automatically handles Telegram's 64-byte `callback_data` limit.
- **Hybrid Storage** &mdash; inline, short-term (TTL), and persistent storage strategies, chosen automatically by payload size.
- **Unlimited Nesting** &mdash; build complex multi-level menus with breadcrumb support.
- **Async-First** &mdash; built for modern `async`/`await` patterns.
- **Pluggable Storage** &mdash; bring your own storage backend.
- **Flexible Layouts** &mdash; grid layouts, custom columns, and navigation buttons.

## Quick Example

```python
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from telegram_menu_builder import MenuBuilder, MenuRouter

router = MenuRouter()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a settings menu."""
    menu = (
        MenuBuilder()
        .add_item("🌍 Language", handler="select_language")
        .add_item("👤 Profile", handler="show_profile")
        .add_item("🔔 Notifications", handler="toggle_notifications")
        .columns(2)
        .add_exit_button(text="❌ Close", handler="close_menu")
        .build()
    )
    await update.message.reply_text("⚙️ Settings", reply_markup=menu)


@router.handler("select_language")
async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict) -> None:
    await update.callback_query.answer("Pick a language")


app = Application.builder().token("YOUR_TOKEN").build()
app.add_handler(CallbackQueryHandler(router.route))
```

## Where to next

- [Quick Start](quickstart.md) &mdash; get a working bot in a few minutes.
- [Guides](guide/menu-building.md) &mdash; menu building, routing, ConversationHandler integration, and storage.
- [API Reference](api/builder.md) &mdash; the full `MenuBuilder`, `MenuRouter`, types, encoding, and storage APIs.
