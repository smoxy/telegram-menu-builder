"""Testing helpers for driving menus and routers without a live Telegram bot.

This module provides small, dependency-free utilities (stdlib :mod:`unittest.mock`
only) for exercising a :class:`~telegram_menu_builder.router.MenuRouter` and
asserting properties of built menus in unit tests:

- :func:`simulate_tap` fabricates a callback ``Update`` from mocks and routes it.
- :func:`tap` is a convenience that encodes a handler + params, then simulates the tap.
- :func:`assert_inline` verifies every button of a menu is an inline callback ref
  (no storage spill), accepting a :class:`~telegram_menu_builder.builder.MenuBuilder`,
  a :class:`telegram.InlineKeyboardMarkup`, or a raw Bot API ``dict``.

It is a submodule and is intentionally *not* exported from the package's eager
``__all__``; import it explicitly with ``import telegram_menu_builder.testing``.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock

from telegram import Update
from telegram.ext import ContextTypes

from telegram_menu_builder.router import MenuRouter
from telegram_menu_builder.types import MenuAction

if TYPE_CHECKING:
    from telegram import InlineKeyboardMarkup

    from telegram_menu_builder.builder import MenuBuilder

# Signature of a router error-handler callback (mirrors MenuRouter's internal type).
ErrorHandlerFunc = Callable[[Update, ContextTypes.DEFAULT_TYPE, Exception], Awaitable[None]]


# Inline callback-data prefixes (uncompressed / compressed). A button is "inline"
# only when its callback_data starts with one of these — storage refs (S:/P:) are not.
_INLINE_PREFIXES = ("I:", "IC:")


@dataclass(frozen=True)
class TapResult:
    """Outcome of simulating a callback-query tap against a router.

    Attributes:
        answered: Whether the router answered the callback query (``answer`` was
            called on the fabricated callback query).
        answer_text: The text passed to ``answer`` (``None`` when answered with no
            text, or when not answered at all).
        edited_text: The text a handler edited the message to via
            ``edit_message_text`` (``None`` when no edit occurred).
        handler_error: The exception raised during routing, if any, captured via
            the router's error middleware (``None`` on success).
    """

    answered: bool
    answer_text: str | None
    edited_text: str | None
    handler_error: Exception | None


def _first_text_arg(call_args: Any) -> str | None:
    """Extract the first positional/text argument from a mock ``call_args``.

    Args:
        call_args: The ``call_args`` attribute of a called mock, or ``None`` if the
            mock was never called.

    Returns:
        The first positional argument as a string, or ``None`` if the mock was not
        called or was called without a positional argument.
    """
    if call_args is None:
        return None
    args, _ = call_args
    if not args:
        return None
    value = args[0]
    return value if isinstance(value, str) else str(value)


async def simulate_tap(
    router: MenuRouter,
    callback_data: str,
    *,
    user_id: int = 1,
    context: Any | None = None,
) -> TapResult:
    """Simulate a user tapping a button and route it through ``router``.

    A mock :class:`telegram.Update` is fabricated whose ``callback_query`` carries
    ``callback_data`` and whose ``answer``/``edit_message_text`` are
    :class:`~unittest.mock.AsyncMock` spies, and whose ``effective_user.id`` is
    ``user_id``. The update is passed to :meth:`MenuRouter.route` and a
    :class:`TapResult` is derived from the spies. Nothing here requires a live bot.

    Any exception raised while routing is captured via a temporary error handler
    registered on the router and surfaced as :attr:`TapResult.handler_error` (the
    router itself swallows handler exceptions, so this is how it is observed).

    Args:
        router: The router under test.
        callback_data: The encoded callback data to deliver (as Telegram would).
        user_id: The id exposed on ``update.effective_user`` (defaults to ``1``).
        context: An optional bot context; a :class:`~unittest.mock.MagicMock` is
            used when ``None``.

    Returns:
        A :class:`TapResult` describing whether the query was answered, the answer
        text, any edited message text, and any handler error.
    """
    callback_query = MagicMock()
    callback_query.data = callback_data
    callback_query.answer = AsyncMock()
    callback_query.edit_message_text = AsyncMock()

    update = MagicMock()
    update.callback_query = callback_query
    update.effective_user = MagicMock()
    update.effective_user.id = user_id

    captured: list[Exception] = []

    async def _capture_error(_update: Any, _context: Any, error: Exception) -> None:
        captured.append(error)

    # Register a transient error handler so a swallowed routing error surfaces as
    # TapResult.handler_error, then unregister it so the router is left untouched.
    # The router exposes no public removal for error handlers, so the internal list
    # is snapshotted and restored; cast keeps the loosely-typed lookup type-clean.
    error_handlers = cast("list[ErrorHandlerFunc]", getattr(router, "_error_handlers", []))
    original = list(error_handlers)
    router.on_error(_capture_error)
    try:
        await router.route(update, context if context is not None else MagicMock())
    finally:
        error_handlers[:] = original

    return TapResult(
        answered=bool(callback_query.answer.called),
        answer_text=_first_text_arg(callback_query.answer.call_args),
        edited_text=_first_text_arg(callback_query.edit_message_text.call_args),
        handler_error=captured[0] if captured else None,
    )


async def tap(router: MenuRouter, handler: str, /, **params: Any) -> TapResult:
    """Encode a handler + params and simulate tapping the resulting button.

    This is a convenience over :func:`simulate_tap`: it builds a
    :class:`~telegram_menu_builder.types.MenuAction` from ``handler``/``params``,
    encodes it with the router's encoder (spilling to storage if needed, exactly as
    a real menu would), then routes the encoded callback data.

    Args:
        router: The router under test.
        handler: The handler name to invoke.
        **params: Parameters to encode into the callback data.

    Returns:
        A :class:`TapResult` describing the routed tap (see :func:`simulate_tap`).
    """
    callback_data = await router.encoder.encode(MenuAction(handler=handler, params=params))
    return await simulate_tap(router, callback_data)


def assert_inline(target: "MenuBuilder | InlineKeyboardMarkup | dict[str, Any]") -> None:
    """Assert every button of ``target`` is an inline callback ref (no storage spill).

    A button passes when it carries ``callback_data`` that is at most 64 bytes and
    is prefixed ``I:`` or ``IC:`` (an inline payload). URL buttons and storage refs
    (``S:``/``P:``) fail: this helper exists to prove a menu is fully self-contained
    and needs no storage backend at runtime.

    The target may be any of:

    - a :class:`~telegram_menu_builder.builder.MenuBuilder` — its own
      :meth:`~telegram_menu_builder.builder.MenuBuilder.assert_inline` pre-flight is
      run and then its synchronous, storage-free
      :meth:`~telegram_menu_builder.builder.MenuBuilder.to_markup` is inspected;
    - a :class:`telegram.InlineKeyboardMarkup` — its ``inline_keyboard`` is inspected;
    - a raw Bot API ``dict`` — its ``"inline_keyboard"`` list is inspected.

    Args:
        target: The menu to verify.

    Raises:
        AssertionError: If any button is missing inline callback data, exceeds the
            64-byte limit, or carries a storage reference instead of an inline payload.
        TypeError: If ``target`` is not a supported type.
    """
    # Local import to avoid importing the builder at module import time and to keep
    # the runtime isinstance check honest.
    from telegram_menu_builder.builder import MenuBuilder

    if isinstance(target, MenuBuilder):
        target.assert_inline()
        rows: list[list[Any]] = [list(row) for row in target.to_markup().inline_keyboard]
        for row in rows:
            for button in row:
                _assert_inline_button(getattr(button, "callback_data", None), button.text)
        return

    if isinstance(target, dict):
        raw_rows: Any = target.get("inline_keyboard")
        if raw_rows is None:
            raise AssertionError("dict target has no 'inline_keyboard' key")
        for raw_row in raw_rows:
            for raw_button in raw_row:
                _assert_inline_button(
                    raw_button.get("callback_data"), raw_button.get("text", "<unknown>")
                )
        return

    keyboard = getattr(target, "inline_keyboard", None)
    if keyboard is None:
        kind = type(target).__name__
        raise TypeError(
            f"assert_inline expects a MenuBuilder, InlineKeyboardMarkup, or Bot API dict, got {kind}"
        )
    for row in keyboard:
        for button in row:
            _assert_inline_button(getattr(button, "callback_data", None), button.text)


def _assert_inline_button(callback_data: Any, text: Any) -> None:
    """Assert a single button's callback data is an inline ref.

    Args:
        callback_data: The button's callback data (may be ``None`` for URL buttons).
        text: The button text, used only for error messages.

    Raises:
        AssertionError: If the callback data is missing, oversized, or not an inline
            (``I:``/``IC:``) payload.
    """
    if not isinstance(callback_data, str) or not callback_data:
        raise AssertionError(f"Button {text!r} has no inline callback_data (URL or empty button)")
    size = len(callback_data.encode("utf-8"))
    if size > 64:
        raise AssertionError(
            f"Button {text!r} callback_data is {size}B, exceeding the 64-byte limit"
        )
    if not callback_data.startswith(_INLINE_PREFIXES):
        ref = callback_data[:2]
        detail = "it would require a storage backend at runtime"
        msg = f"Button {text!r} carries a storage reference ({ref!r}), not an inline payload; {detail}"
        raise AssertionError(msg)
