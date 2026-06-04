# Application-free Menus

Most of this library is built around an async [`MenuRouter`](routing.md) and a
[storage backend](storage.md). But sometimes you just want a keyboard: one menu
definition, no PTB `Application`, no event loop, no storage. A microservice that only
*renders* a menu and hands the JSON to another process, a serverless function that
calls the Bot API by hand, a unit test that asserts a layout — none of these want to
spin up an `Application` or an async storage backend.

For exactly those cases [`MenuBuilder`][telegram_menu_builder.MenuBuilder] offers two
**synchronous, storage-free** terminal methods:

- [`to_markup()`][telegram_menu_builder.builder.MenuBuilder.to_markup] returns a
  `telegram.InlineKeyboardMarkup` ready to pass to python-telegram-bot.
- [`to_raw()`][telegram_menu_builder.builder.MenuBuilder.to_raw] returns a plain Telegram
  Bot API dict — `{"inline_keyboard": [[...]]}` — that you can serialize and POST
  yourself, with no PTB object in sight.

Both run no `await`, touch no storage backend, and spawn no worker thread, so they are
safe to call from an ordinary synchronous function.

!!! note "When to reach for `build_async()` instead"
    `to_markup()`/`to_raw()` only emit **inline** callbacks (the payload rides in the
    64-byte `callback_data`). They cannot spill to storage. If a menu carries enough
    state to overflow the inline budget, use the async builder —
    [`await build_async()`](menu-building.md) — with a [storage backend](storage.md).
    See [Storage strategies](storage.md#strategy-selection) for the byte budget.

## Quick start

Define the menu once, render it synchronously. The same builder definition works
whether you want a PTB object or a raw dict:

```python
from telegram_menu_builder import MenuBuilder

builder = (
    MenuBuilder()
    .add_item("Settings", handler="open_settings", section="general")
    .add_item("Profile", handler="open_profile")
    .columns(2)
)

markup = builder.to_markup()   # telegram.InlineKeyboardMarkup
# or, with no python-telegram-bot object at all:
raw = builder.to_raw()
# {"inline_keyboard": [[
#     {"text": "Settings", "callback_data": "I:..."},
#     {"text": "Profile",  "callback_data": "I:..."},
# ]]}
```

`to_raw()` is JSON-serializable as-is, so a service that talks to the Bot API directly
can send it straight through as `reply_markup`:

```python
import json

import httpx

payload = {
    "chat_id": chat_id,
    "text": "Choose an option:",
    "reply_markup": json.dumps(builder.to_raw()),
}
httpx.post(f"https://api.telegram.org/bot{token}/sendMessage", data=payload)
```

URL buttons render as `{"text": ..., "url": ...}` and carry no `callback_data`, exactly
as the Bot API expects.

!!! tip "One definition, shared across codebases"
    Because `to_raw()` returns a plain dict with no library types in it, the *same*
    `MenuBuilder` definition can be authored once and consumed by a PTB bot
    (`to_markup()`), a raw-HTTP service (`to_raw()`), and a test suite alike. The menu
    is the single source of truth; the renderer is the caller's choice.

## Enforcing the inline budget

A storage-free menu is only valid if **every** item fits inline. Two mechanisms make
that guarantee explicit rather than accidental.

### `on_oversize="error"`

By default a `MenuBuilder` is created with `on_oversize="spill"`: an oversize callback
is written to storage and referenced by a short key. For application-free menus that
silent spill is the wrong behavior — it would quietly require a storage backend at
runtime. Construct the builder with `on_oversize="error"` to make an overflowing item a
hard error at build time instead:

```python
builder = MenuBuilder(on_oversize="error")
builder.add_item("Open", handler="open", payload="x" * 200)  # far too big for inline

builder.to_markup()   # raises EncodingError — this item cannot stay inline
```

The same policy applies to `build_async()`: with `on_oversize="error"` an item that
would spill raises [`EncodingError`][telegram_menu_builder.EncodingError] there too,
rather than reaching for storage. Reserve `build_async()` (with the default `"spill"`)
for menus that genuinely need storage-backed callbacks.

### `assert_inline()`

[`assert_inline()`][telegram_menu_builder.builder.MenuBuilder.assert_inline] is a cheap
pre-flight: it runs the inline-only encoder over every pending item and navigation
button but assembles no keyboard. It raises `EncodingError` for the first item whose
callback data would not fit inline, so you can fail fast — for example in a test —
before handing the menu to `to_markup()`:

```python
builder.assert_inline()   # raises EncodingError on the first oversize item
markup = builder.to_markup()
```

!!! note "`assert_inline()` vs the testing helper"
    `MenuBuilder.assert_inline()` checks *pending specs* and raises `EncodingError`.
    The [testing](testing.md) module also exposes a module-level
    [`assert_inline()`][telegram_menu_builder.testing.assert_inline] that inspects a
    *built* menu (a `MenuBuilder`, an `InlineKeyboardMarkup`, or a raw dict) and raises
    `AssertionError`. Use the builder method to guard production code; use the testing
    helper to assert a menu in a unit test.

## See also

- [Menu Building](menu-building.md) — the full fluent builder API and `build_async()`.
- [Storage backends](storage.md) — the three-tier strategy and when callbacks spill.
- [Testing](testing.md) — drive handlers and assert menus stay inline, with no live bot.
- [Builder API reference](../api/builder.md) — generated reference for `MenuBuilder`.
