# FAQ

Short answers to recurring questions. For the long form, follow the links into the
[guides](guide/menu-building.md).

## Does the library escape message text for me?

No — and it does not need to. This library builds **keyboards**, not message text.
`MenuBuilder` produces an `InlineKeyboardMarkup` (or, with
[`to_raw()`](guide/menu-building.md), a plain Bot API dict); the message body you pass to
`reply_text` / `edit_message_text` is entirely yours. Button **labels** are sent as
literal `text` and are never parsed as Markdown or HTML, so they need no escaping either.

Escaping only matters for the **message text** when you send it with a `parse_mode`, and
that is the caller's responsibility. Use the stdlib and python-telegram-bot helpers
rather than hand-rolling it:

```python
import html

from telegram.helpers import escape_markdown

# MarkdownV2 — escape every dynamic fragment you interpolate.
safe_md = escape_markdown(user_name, version=2)
await update.message.reply_text(
    f"Welcome, {safe_md}\\!", parse_mode="MarkdownV2"
)

# HTML — stdlib html.escape covers the reserved characters.
safe_html = html.escape(user_name)
await update.message.reply_text(
    f"Welcome, <b>{safe_html}</b>", parse_mode="HTML"
)
```

!!! note "Always pass `version=2` to `escape_markdown`"
    `telegram.helpers.escape_markdown` defaults to the **legacy** Markdown rules. Telegram's
    current dialect is MarkdownV2, which escapes a larger reserved set (`_ * [ ] ( ) ~ ` > #
    + - = | { } . !`), so pass `version=2` explicitly to match the `parse_mode="MarkdownV2"`
    you send. For HTML, the stdlib `html.escape` is enough.

!!! tip "Plain text needs nothing"
    If you do not pass a `parse_mode`, Telegram treats the message as literal text and there
    is nothing to escape — the simplest and safest default.
