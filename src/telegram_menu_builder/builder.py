"""Menu builder - Fluent API for constructing inline keyboard menus.

This module provides the main MenuBuilder class that implements the builder pattern
for creating complex, nested inline keyboard menus with ease.
"""

import asyncio
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Self

from telegram import InlineKeyboardMarkup

from telegram_menu_builder.encoding import CallbackEncoder
from telegram_menu_builder.storage import MemoryStorage, StorageBackend
from telegram_menu_builder.types import (
    LayoutConfig,
    MenuAction,
    MenuItem,
    NavigationButton,
    NavigationConfig,
    ValidationError,
)


@dataclass
class _CallbackItemSpec:
    """A pending callback menu item awaiting encoding at build time."""

    text: str
    handler: str
    params: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class _UrlItemSpec:
    """A pending URL menu item (no callback data to encode)."""

    text: str
    url: str


_ItemSpec = _CallbackItemSpec | _UrlItemSpec


class MenuBuilder:
    """Fluent builder for creating inline keyboard menus.

    This class provides a chainable API for constructing menus with support for:
    - Unlimited parameters per button
    - Automatic callback data encoding
    - Grid layouts with configurable columns
    - Navigation buttons (back, next, exit)
    - Nested submenus with breadcrumb tracking

    Attributes:
        storage: Storage backend for callback data
        encoder: Callback data encoder
        items: List of menu items
        layout: Layout configuration
        navigation: Navigation configuration

    Example:
        >>> builder = MenuBuilder()
        >>> menu = (builder
        ...     .add_item("Option 1", handler="handle_1", user_id=123)
        ...     .add_item("Option 2", handler="handle_2")
        ...     .columns(2)
        ...     .add_back_button()
        ...     .build())
    """

    def __init__(self, storage: StorageBackend | None = None, menu_id: str | None = None) -> None:
        """Initialize menu builder.

        Args:
            storage: Storage backend (defaults to MemoryStorage)
            menu_id: Optional menu identifier for tracking
        """
        self._storage = storage or MemoryStorage()
        self._encoder = CallbackEncoder(self._storage)
        self._menu_id = menu_id

        self._items: list[_ItemSpec] = []
        self._submenus: dict[int, MenuBuilder] = {}
        self._layout = LayoutConfig()
        self._navigation = NavigationConfig()

    def add_item(self, text: str, handler: str, **params: Any) -> Self:
        """Add a menu item with arbitrary parameters.

        Args:
            text: Button display text
            handler: Handler function name to call
            **params: Arbitrary parameters to pass to handler

        Returns:
            Self for chaining

        Example:
            >>> builder.add_item(
            ...     "Edit User",
            ...     handler="edit_user",
            ...     user_id=123,
            ...     field="email",
            ...     breadcrumb=["settings", "users"]
            ... )
        """
        self._items.append(_CallbackItemSpec(text=text, handler=handler, params=dict(params)))
        return self

    def add_items(self, items: Sequence[tuple[str, str, dict[str, Any]]]) -> Self:
        """Add multiple menu items at once.

        Args:
            items: Sequence of (text, handler, params) tuples

        Returns:
            Self for chaining

        Example:
            >>> builder.add_items([
            ...     ("Option 1", "handle_1", {"id": 1}),
            ...     ("Option 2", "handle_2", {"id": 2}),
            ... ])
        """
        for text, handler, params in items:
            self.add_item(text, handler, **params)
        return self

    def add_url_button(self, text: str, url: str) -> Self:
        """Add a URL button (no callback, opens URL).

        Args:
            text: Button display text
            url: URL to open

        Returns:
            Self for chaining

        Example:
            >>> builder.add_url_button("Visit Website", "https://example.com")
        """
        self._items.append(_UrlItemSpec(text=text, url=url))
        return self

    def add_submenu(
        self, text: str, submenu: "MenuBuilder", handler: str = "_submenu", **params: Any
    ) -> Self:
        """Add a button that opens a submenu.

        The submenu builder will be stored and can be built later.

        Args:
            text: Button display text
            submenu: MenuBuilder instance for the submenu
            handler: Handler name (default: "_submenu")
            **params: Additional parameters

        Returns:
            Self for chaining

        Example:
            >>> submenu = MenuBuilder().add_item("Sub option", "handle_sub")
            >>> builder.add_submenu("Open submenu", submenu)
        """
        # Register the submenu in an internal registry keyed by id(). Only the
        # JSON-serializable integer id is placed in params; the builder object
        # itself must never leak into encoded callback data (it is not
        # JSON-serializable and would fail MenuAction validation).
        submenu_id = id(submenu)
        self._submenus[submenu_id] = submenu
        params["_submenu_id"] = submenu_id

        return self.add_item(text, handler, **params)

    def get_submenu(self, submenu_id: int) -> "MenuBuilder | None":
        """Return a submenu builder previously registered via :meth:`add_submenu`.

        Args:
            submenu_id: The ``id()`` of the submenu builder, as stored in a
                button's ``_submenu_id`` parameter.

        Returns:
            The registered MenuBuilder, or None if no submenu matches.
        """
        return self._submenus.get(submenu_id)

    def columns(self, n: int) -> Self:
        """Set number of columns in the grid layout.

        Args:
            n: Number of columns (1-8)

        Returns:
            Self for chaining

        Raises:
            ValidationError: If n is out of range

        Example:
            >>> builder.columns(3)  # 3 buttons per row
        """
        if not 1 <= n <= 8:
            raise ValidationError(f"Columns must be between 1 and 8, got {n}")

        self._layout.columns = n
        return self

    def max_rows(self, n: int | None) -> Self:
        """Set maximum number of rows.

        Args:
            n: Maximum rows (None for unlimited)

        Returns:
            Self for chaining

        Example:
            >>> builder.max_rows(5)  # Max 5 rows
        """
        if n is not None and n < 1:
            raise ValidationError(f"max_rows must be >= 1 or None, got {n}")

        self._layout.max_rows = n
        return self

    def _set_nav_button(self, slot: str, text: str, handler: str, params: dict[str, Any]) -> Self:
        """Set a navigation button slot on the navigation config.

        Args:
            slot: One of ``back_button``, ``next_button``, ``exit_button``, ``cancel_button``.
            text: Button text.
            handler: Handler function name.
            params: Additional handler parameters.

        Returns:
            Self for chaining.
        """
        button = NavigationButton(text=text, handler=handler, params=params)
        match slot:
            case "back_button":
                self._navigation.back_button = button
            case "next_button":
                self._navigation.next_button = button
            case "exit_button":
                self._navigation.exit_button = button
            case "cancel_button":
                self._navigation.cancel_button = button
            case _:  # pragma: no cover - internal callers only pass known slots
                raise ValueError(f"Unknown navigation slot: {slot}")
        return self

    def add_back_button(
        self, text: str = "🔙 Back", handler: str = "go_back", **params: Any
    ) -> Self:
        """Add a back navigation button.

        Args:
            text: Button text
            handler: Handler name
            **params: Additional parameters

        Returns:
            Self for chaining

        Example:
            >>> builder.add_back_button(handler="return_to_menu", page=1)
        """
        return self._set_nav_button("back_button", text, handler, params)

    def add_next_button(
        self, text: str = "➡️ Next", handler: str = "go_next", **params: Any
    ) -> Self:
        """Add a next navigation button.

        Args:
            text: Button text
            handler: Handler name
            **params: Additional parameters

        Returns:
            Self for chaining

        Example:
            >>> builder.add_next_button(handler="next_page", page=2)
        """
        return self._set_nav_button("next_button", text, handler, params)

    def add_exit_button(
        self, text: str = "❌ Exit", handler: str = "exit_menu", **params: Any
    ) -> Self:
        """Add an exit button.

        Args:
            text: Button text
            handler: Handler name
            **params: Additional parameters

        Returns:
            Self for chaining

        Example:
            >>> builder.add_exit_button()
        """
        return self._set_nav_button("exit_button", text, handler, params)

    def add_cancel_button(
        self, text: str = "🚫 Cancel", handler: str = "cancel", **params: Any
    ) -> Self:
        """Add a cancel button.

        Args:
            text: Button text
            handler: Handler name
            **params: Additional parameters

        Returns:
            Self for chaining

        Example:
            >>> builder.add_cancel_button(handler="cancel_operation")
        """
        return self._set_nav_button("cancel_button", text, handler, params)

    def build(self) -> InlineKeyboardMarkup:
        """Build the final InlineKeyboardMarkup.

        This is a synchronous convenience wrapper around :meth:`build_async` that
        encodes all callback data and assembles the keyboard.

        When called outside an event loop it drives the async build directly. When
        called from within a running event loop (e.g. inside an async handler) the
        async build is executed on a short-lived worker thread so this synchronous
        API keeps working. In async code, prefer ``await build_async()`` directly.

        Returns:
            InlineKeyboardMarkup ready to use with python-telegram-bot

        Raises:
            ValidationError: If menu configuration is invalid

        Example:
            >>> menu = builder.build()
            >>> await update.message.reply_text("Choose:", reply_markup=menu)
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running loop: safe to drive the async build directly.
            return asyncio.run(self.build_async())

        # A loop is already running in this thread: run the async build on a
        # dedicated worker thread (with its own event loop) and wait for it.
        result: list[InlineKeyboardMarkup] = []
        error: list[Exception] = []

        def _runner() -> None:
            try:
                result.append(asyncio.run(self.build_async()))
            except Exception as exc:  # re-raised on the calling thread below
                error.append(exc)

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()

        if error:
            raise error[0]
        return result[0]

    async def build_async(self) -> InlineKeyboardMarkup:
        """Build the final InlineKeyboardMarkup (async version).

        Returns:
            InlineKeyboardMarkup ready to use

        Raises:
            ValidationError: If menu configuration is invalid
        """
        if not self._items and not self._has_navigation_buttons():
            raise ValidationError("Cannot build empty menu (no items or navigation buttons)")

        # Encode all pending item specs into MenuItems. Encoding is deferred from
        # the add_* calls to here so that it always runs inside an async context
        # (this is what guarantees non-empty callback_data, see build()).
        items: list[MenuItem] = []
        for spec in self._items:
            if isinstance(spec, _UrlItemSpec):
                items.append(MenuItem(text=spec.text, url=spec.url))
            else:
                items.append(
                    await self._create_menu_item_async(spec.text, spec.handler, spec.params)
                )

        # Build keyboard layout
        keyboard: list[list[MenuItem]] = []

        # Arrange items in grid
        current_row: list[MenuItem] = []
        for item in items:
            current_row.append(item)

            # Check if row is complete
            if len(current_row) >= self._layout.columns:
                keyboard.append(current_row)
                current_row = []

            # Check max rows limit
            if self._layout.max_rows and len(keyboard) >= self._layout.max_rows:
                break

        # Add remaining items
        if current_row:
            keyboard.append(current_row)

        # Add navigation buttons
        nav_rows = await self._build_navigation_buttons()
        keyboard.extend(nav_rows)

        # Convert to Telegram format
        telegram_keyboard = [[item.to_telegram_button() for item in row] for row in keyboard]

        return InlineKeyboardMarkup(telegram_keyboard)

    async def _create_menu_item_async(
        self, text: str, handler: str, params: dict[str, Any]
    ) -> MenuItem:
        """Create a MenuItem with encoded callback data (async version)."""
        action = MenuAction(handler=handler, params=params)
        callback_data = await self._encoder.encode(action)

        return MenuItem(text=text, callback_data=callback_data)

    async def _build_navigation_buttons(self) -> list[list[MenuItem]]:
        """Build navigation button rows."""
        rows: list[list[MenuItem]] = []

        # Back/Next buttons (same row)
        back_next_row: list[MenuItem] = []

        if self._navigation.back_button:
            item = await self._create_menu_item_async(
                self._navigation.back_button.text,
                self._navigation.back_button.handler,
                self._navigation.back_button.params,
            )
            back_next_row.append(item)

        if self._navigation.next_button:
            item = await self._create_menu_item_async(
                self._navigation.next_button.text,
                self._navigation.next_button.handler,
                self._navigation.next_button.params,
            )
            back_next_row.append(item)

        if back_next_row:
            rows.append(back_next_row)

        # Exit/Cancel button (separate row)
        if self._navigation.exit_button:
            item = await self._create_menu_item_async(
                self._navigation.exit_button.text,
                self._navigation.exit_button.handler,
                self._navigation.exit_button.params,
            )
            rows.append([item])
        elif self._navigation.cancel_button:
            item = await self._create_menu_item_async(
                self._navigation.cancel_button.text,
                self._navigation.cancel_button.handler,
                self._navigation.cancel_button.params,
            )
            rows.append([item])

        return rows

    def _has_navigation_buttons(self) -> bool:
        """Check if any navigation buttons are configured."""
        return any(
            [
                self._navigation.back_button,
                self._navigation.next_button,
                self._navigation.exit_button,
                self._navigation.cancel_button,
            ]
        )

    @property
    def storage(self) -> StorageBackend:
        """Get the storage backend."""
        return self._storage

    @property
    def encoder(self) -> CallbackEncoder:
        """Get the callback encoder."""
        return self._encoder
