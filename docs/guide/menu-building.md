# Building Menus

The [`MenuBuilder`][telegram_menu_builder.MenuBuilder] is the entry point for
constructing inline keyboard menus. It exposes a fluent, chainable API: every
configuration method returns the builder itself, so you can describe an entire
keyboard in a single expression and finish with a call to
[`build()`](#build-vs-build_async) (or `await build_async()`).

```python
from telegram_menu_builder import MenuBuilder

menu = (
    MenuBuilder()
    .add_item("🌍 Language", handler="set_language")
    .add_item("👤 Profile", handler="edit_profile")
    .add_item("🔔 Notifications", handler="notifications")
    .columns(2)
    .add_back_button()
    .build()
)
```

The result is a `telegram.InlineKeyboardMarkup` you can pass straight to
`reply_markup`:

```python
await update.message.reply_text("⚙️ Settings", reply_markup=menu)
```

!!! note "Encoding is deferred"
    Calling `add_item`, `add_back_button`, and friends does **not** encode any
    callback data. The builder records lightweight *specs* and performs all
    encoding when you call `build()` / `build_async()`. See
    [build() vs build_async()](#build-vs-build_async) for why this matters.

## Adding callback items

`add_item(text, handler, **params)` is the workhorse. `text` is the button
label, `handler` is the name the [router](routing.md) will dispatch to, and any
remaining keyword arguments become the handler's `params`.

```python
builder.add_item(
    "📝 Edit User",
    handler="edit_user",
    user_id=123,
    field="email",
    breadcrumb=["settings", "users"],
    validation_required=True,
)
```

!!! warning "Params must be JSON-serializable"
    All values you pass as `**params` are validated for JSON serializability
    when the menu is built. Stick to strings, numbers, booleans, lists, and
    dicts of those. Passing objects, sets, or `datetime` instances raises a
    `ValidationError`. Handler names must be valid Python identifiers (dots are
    allowed for [router groups](routing.md#routergroup-prefixing)).

### Adding several items at once

`add_items` takes a sequence of `(text, handler, params)` tuples. It is a thin
convenience wrapper that calls `add_item` for each entry, so the `params` dict
follows the same rules.

```python
builder.add_items(
    [
        ("Option 1", "handle_1", {"id": 1}),
        ("Option 2", "handle_2", {"id": 2}),
        ("Option 3", "handle_3", {}),
    ]
)
```

## URL buttons

`add_url_button(text, url)` creates a button that opens a link instead of
firing a callback. URL buttons carry no callback data and are never routed.

```python
builder.add_url_button("📖 Docs", "https://example.com/docs")
```

## Submenus

`add_submenu(text, submenu, handler="_submenu", **params)` registers a nested
`MenuBuilder` and adds a button that points at it. The submenu builder is kept
in an internal registry keyed by its `id()`; only that integer id is placed in
the button's params (under `_submenu_id`), so the builder object itself never
leaks into encoded callback data.

```python
user_submenu = (
    MenuBuilder()
    .add_item("Add User", handler="add_user")
    .add_item("List Users", handler="list_users")
    .add_back_button()
)

main_menu = MenuBuilder().add_submenu("👥 Users", user_submenu)
```

In your `_submenu` handler you can recover the registered builder with
`get_submenu(submenu_id)`:

```python
@router.handler("_submenu")
async def open_submenu(update, context, params):
    submenu = main_menu.get_submenu(params["_submenu_id"])
    if submenu is not None:
        await update.callback_query.edit_message_text(
            "Submenu", reply_markup=await submenu.build_async()
        )
```

!!! note
    Submenu registration lives on the *parent* builder instance, so call
    `get_submenu` on the same builder you called `add_submenu` on.

## Layout: columns and rows

By default items flow into a grid three columns wide. Two methods control the
arrangement:

- `columns(n)` — buttons per row, `1`–`8`. Out-of-range values raise
  `ValidationError`.
- `max_rows(n)` — cap the number of *item* rows (`None` for unlimited, `>= 1`
  otherwise). Items beyond the limit are dropped.

```python
menu = (
    MenuBuilder()
    .add_item("A", handler="a")
    .add_item("B", handler="b")
    .add_item("C", handler="c")
    .add_item("D", handler="d")
    .columns(2)      # two buttons per row -> 2 rows
    .max_rows(5)     # never exceed 5 item rows
    .build()
)
```

!!! note "max_rows counts item rows only"
    The `max_rows` cap is applied while laying out callback/URL items.
    Navigation buttons are appended afterwards and are not counted against the
    limit.

## Navigation buttons

Navigation buttons are configured independently of the item grid and are always
rendered *after* the items. Each accepts the same `text`, `handler`, and
`**params` shape as `add_item`, with sensible defaults.

| Method | Default text | Default handler | Placement |
| --- | --- | --- | --- |
| `add_back_button` | `🔙 Back` | `go_back` | back/next row |
| `add_next_button` | `➡️ Next` | `go_next` | back/next row |
| `add_exit_button` | `❌ Exit` | `exit_menu` | own row |
| `add_cancel_button` | `🚫 Cancel` | `cancel` | own row |

Layout rules:

- **Back and Next share one row**, in that order. Either may be present alone.
- **Exit and Cancel each get their own row.** They are mutually exclusive —
  configuring both raises a `ValidationError` (`Cannot have both exit_button and
  cancel_button`). If both somehow end up set, `exit` wins at render time.

```python
menu = (
    MenuBuilder()
    .add_item("Item 1", handler="h1")
    .add_item("Item 2", handler="h2")
    .add_back_button(handler="list_users", page=2)
    .add_next_button(handler="list_users", page=4)
    .add_exit_button()  # NOT together with add_cancel_button
    .build()
)
```

A menu with **only** navigation buttons (no items) is valid. A menu with neither
items nor navigation buttons raises `ValidationError` ("Cannot build empty
menu") when built.

## build() vs build_async()

Encoding callback data is asynchronous (the storage backend is awaited), and
the builder defers *all* encoding to build time. This gives you two entry
points.

### `build_async()` — the real implementation

`build_async()` is the canonical builder. It encodes every pending item spec
inside an async context, arranges the grid, appends navigation rows, and returns
the `InlineKeyboardMarkup`. **Inside an async handler, always prefer it:**

```python
async def show_menu(update, context):
    menu = await (
        MenuBuilder()
        .add_item("Option 1", handler="h1")
        .add_back_button()
        .build_async()
    )
    await update.message.reply_text("Choose:", reply_markup=menu)
```

### `build()` — the sync convenience wrapper

`build()` exists so menus can be assembled from synchronous code. Its behaviour
depends on whether an event loop is already running on the calling thread:

- **No running loop** → it drives the async build directly via
  `asyncio.run(build_async())`.
- **A loop is already running** (e.g. you called it from inside an `async def`
  handler) → it cannot reuse that loop, so it runs `build_async()` on a
  short-lived **worker thread** with its own event loop and blocks until the
  thread finishes, re-raising any exception on the calling thread.

```python
# Synchronous context (scripts, tests) — fine:
menu = MenuBuilder().add_item("Go", handler="go").build()
```

!!! warning "Inside async handlers, use `await build_async()`"
    Calling the blocking `build()` from within a running event loop spins up a
    worker thread for every menu. It works, but it blocks the calling
    coroutine and adds avoidable overhead. In any `async def` code path, write
    `await builder.build_async()` instead.

## See also

- [Routing callbacks](routing.md) — dispatch the `handler`/`params` you encode
  here.
- [Storage strategies](storage.md) — where large callbacks are stored.
- [Encoding internals](../advanced/encoding.md) — how params become
  `callback_data`.
