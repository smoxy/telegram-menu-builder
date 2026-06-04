# Testing

Testing a menu bot usually means one of two things: *does tapping this button run the
right handler?* and *does this menu stay inline so it needs no storage at runtime?* The
[`telegram_menu_builder.testing`][telegram_menu_builder.testing] module answers both
with small, dependency-free helpers (stdlib `unittest.mock` only) that
drive a [`MenuRouter`](routing.md) and assert properties of built menus — **with no live
Telegram bot, no network, and no `Application`**.

!!! note "Import it explicitly"
    The testing module is intentionally **not** exported from the package's eager
    `__all__`, so it never loads in normal use. Import the submodule directly in your
    tests:

    ```python
    import telegram_menu_builder.testing as tmb_testing
    # or
    from telegram_menu_builder.testing import simulate_tap, tap, assert_inline
    ```

## Driving a tap

[`simulate_tap(router, callback_data)`][telegram_menu_builder.testing.simulate_tap]
fabricates a callback-query `Update` from mocks, delivers it to
[`MenuRouter.route`][telegram_menu_builder.router.MenuRouter.route], and returns a
[`TapResult`][telegram_menu_builder.testing.TapResult] describing what happened. The
update's `callback_query.answer` and `edit_message_text` are
[`AsyncMock`](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock)
spies, and `effective_user.id` is the `user_id` argument (default `1`):

```python
from telegram_menu_builder import MenuRouter
from telegram_menu_builder.testing import simulate_tap

router = MenuRouter()


@router.handler("greet")
async def greet(update, context, params):
    await update.callback_query.answer(f"Hello {params['name']}!")


async def test_greet():
    # Deliver the exact callback_data Telegram would send.
    result = await simulate_tap(router, "I:...")
    assert result.answered
    assert result.answer_text == "Hello Ada!"
```

`TapResult` exposes everything a test usually checks:

| Field | Meaning |
| --- | --- |
| `answered` | Whether the router answered the callback query. |
| `answer_text` | The text passed to `answer` (`None` if answered with no text). |
| `edited_text` | The text a handler edited the message to via `edit_message_text`. |
| `handler_error` | The exception raised during routing, if any. |

!!! note "Handler errors are captured, not raised"
    `MenuRouter` swallows handler exceptions (routing one bad tap should not crash the
    bot). `simulate_tap` registers a transient error handler so a swallowed error
    surfaces as `TapResult.handler_error` instead — then removes it, leaving the router
    untouched. Assert on `result.handler_error` to test failure paths.

## Tapping by handler + params

You rarely have the encoded `callback_data` on hand in a test — you have a handler name
and some params. [`tap(router, handler, **params)`][telegram_menu_builder.testing.tap]
closes that gap: it encodes a [`MenuAction`][telegram_menu_builder.MenuAction] with the
router's own encoder (spilling to storage exactly as a real menu would), then routes the
result. It mirrors the builder's `add_item(text, handler="h", **params)` calling style:

```python
from telegram_menu_builder.testing import tap


async def test_greet_by_name():
    result = await tap(router, "greet", name="Ada")
    assert result.answered
    assert result.answer_text == "Hello Ada!"
```

Because `tap` encodes through the router's encoder, a handler that relies on a
storage-backed (`Short`/`Persistent`) callback is exercised end-to-end: the params spill
to the router's storage on encode and are read back on route, just as in production.

## Asserting a menu stays inline

[`assert_inline(target)`][telegram_menu_builder.testing.assert_inline] proves a menu is
fully self-contained — every button carries an inline (`I:`/`IC:`) callback payload of
at most 64 bytes, with no storage reference (`S:`/`P:`) and no missing data. It is the
test-suite counterpart to building an [application-free menu](static-menus.md): if
`assert_inline` passes, the menu needs no storage backend at runtime.

The `target` may be a [`MenuBuilder`][telegram_menu_builder.MenuBuilder], a
`telegram.InlineKeyboardMarkup`, or a raw Bot API `dict`:

```python
from telegram_menu_builder import MenuBuilder
from telegram_menu_builder.testing import assert_inline

builder = (
    MenuBuilder()
    .add_item("Settings", handler="open_settings", section="general")
    .add_item("Profile", handler="open_profile")
)

assert_inline(builder)              # checks the builder (runs its own pre-flight)
assert_inline(builder.to_markup())  # checks a built InlineKeyboardMarkup
assert_inline(builder.to_raw())     # checks a raw Bot API dict
```

When a button would spill, the assertion is specific about why — it names the button and
whether the data is oversized, missing, or carries a storage reference:

```text
AssertionError: Button 'Open' carries a storage reference ('S:'), not an inline
payload; it would require a storage backend at runtime
```

!!! note "Two `assert_inline`s, two failure modes"
    `MenuBuilder.assert_inline()` is a production-side guard that raises
    [`EncodingError`][telegram_menu_builder.EncodingError] over *pending* specs (see
    [Application-free Menus](static-menus.md#assert_inline)). The testing module's
    `assert_inline()` is a test-side assertion that raises `AssertionError` over a
    *built* menu. Use the one that matches where you are checking.

## See also

- [Callback Routing](routing.md) — handlers, middleware, and `route()`.
- [Application-free Menus](static-menus.md) — `to_markup()`/`to_raw()` and the inline
  budget these helpers verify.
- [Storage backends](storage.md) — when callbacks spill, which `tap()` exercises faithfully.
