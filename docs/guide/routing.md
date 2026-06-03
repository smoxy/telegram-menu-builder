# Routing Callbacks

When a user taps an inline button, Telegram sends back the button's
`callback_data`. The [`MenuRouter`][telegram_menu_builder.MenuRouter] decodes
that data into a handler name plus a `params` dict and dispatches it to the
function you registered for that name.

```python
from telegram_menu_builder import MenuRouter

router = MenuRouter()
```

## Wiring the router into your application

Register the router's `route` coroutine with a single `CallbackQueryHandler`.
The router takes care of decoding, dispatching, middleware, and (optionally)
answering the callback query.

```python
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler

app = Application.builder().token("YOUR_TOKEN").build()
app.add_handler(CallbackQueryHandler(router.route))
```

!!! note "One router, one handler"
    You only need one `CallbackQueryHandler(router.route)`. All menu callbacks
    flow through it and are dispatched internally by handler name.

## Handler signature

Every handler is an `async` function with three positional arguments:

```python
from telegram import Update
from telegram.ext import ContextTypes

@router.handler("edit_user")
async def edit_user(update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict) -> None:
    user_id = params["user_id"]
    await update.callback_query.edit_message_text(f"Editing user {user_id}")
```

`params` is exactly the keyword arguments you passed to `add_item` (or a
navigation button) when [building the menu](menu-building.md#adding-callback-items).

## Registering handlers

### The `@router.handler` decorator

The most common way to register a handler is the decorator. Its argument is the
handler name that must match the `handler=` you used in the builder.

```python
@router.handler("set_language")
async def set_language(update, context, params):
    ...
```

### `register_handler` and `register_handlers`

For programmatic registration (or when the function is defined elsewhere), use
`register_handler(name, func)` or register many at once with
`register_handlers(mapping)`:

```python
async def handle_a(update, context, params): ...
async def handle_b(update, context, params): ...

router.register_handler("action_a", handle_a)

router.register_handlers(
    {
        "action_a": handle_a,
        "action_b": handle_b,
    }
)
```

!!! note "Re-registering overwrites"
    Registering a name that already exists overwrites the previous handler and
    logs a warning. Use `unregister_handler(name)` to remove one (it returns
    `True` if something was removed). Inspect the registry with `get_handler(name)`
    and `list_handlers()`.

### The default handler

If no handler matches the decoded name, the router falls back to the default
handler when one is set:

```python
async def fallback(update, context, params):
    await update.callback_query.answer("Action not available", show_alert=True)

router.set_default_handler(fallback)
```

You can also pass it at construction time:
`MenuRouter(default_handler=fallback)`. With no matching handler **and** no
default, the router answers the query with "Action not available" (when
`auto_answer` is on) and stops.

## Middleware

The router supports three middleware hooks. `before` and `after` handlers
receive the same `(update, context, params)` signature as normal handlers;
`on_error` handlers receive `(update, context, error)`.

```python
@router.before
async def log_in(update, context, params):
    logger.info("incoming callback: %s", params)

@router.after
async def log_out(update, context, params):
    logger.info("handler finished")

@router.on_error
async def on_error(update, context, error):
    logger.error("routing failed: %s", error)
    await update.callback_query.answer("Something went wrong")
```

Execution order for a successful dispatch:

1. all `before` middleware (in registration order),
2. the matched handler (or the default handler),
3. all `after` middleware.

!!! note "When middleware runs"
    `before`/`after` only run when an actual handler (or the default handler)
    executes — if no handler matches and there is no default, `after` is
    skipped. `on_error` middleware runs when decoding fails (`DecodingError`,
    e.g. expired short-term data) or when any exception bubbles out of dispatch.

## `auto_answer` behaviour

Telegram expects every callback query to be answered, otherwise the client
shows a spinner. The router answers for you by default (`auto_answer=True`):

- after a handler returns successfully, `callback_query.answer()` is called;
- when no handler matches and there is no default, it answers
  `"Action not available"`;
- when decoding or handling raises, it answers with a short error message after
  running any `on_error` middleware.

Disable it if you want full control (e.g. you call `answer()` yourself, possibly
with `show_alert=True`):

```python
router = MenuRouter(auto_answer=False)
```

!!! warning "Answer the query yourself if you disable auto_answer"
    With `auto_answer=False`, you are responsible for calling
    `update.callback_query.answer()` in every code path, or the user's client
    will keep showing a loading indicator.

## RouterGroup prefixing

`RouterGroup(prefix, router)` lets you namespace handlers by feature. It
prefixes every registered name with `"<prefix>."` and forwards registration to
the parent router, so build menus with the fully-qualified name.

```python
from telegram_menu_builder.router import RouterGroup

users = RouterGroup("users", router)

@users.handler("edit")          # registered as "users.edit"
async def edit_user(update, context, params):
    ...

# In the builder, target the prefixed name:
MenuBuilder().add_item("Edit", handler="users.edit", user_id=1)
```

`RouterGroup` also exposes `register_handler(name, func)`, which applies the
same prefix. Dotted handler names are valid identifiers as far as the encoder is
concerned, so they round-trip through callback data without special handling.

## See also

- [Building menus](menu-building.md) — produce the `handler`/`params` the router
  consumes.
- [Storage strategies](storage.md) — share a backend between builder and router.
- [Encoding internals](../advanced/encoding.md) — what `route` decodes.
