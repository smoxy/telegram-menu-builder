"""Menu builder - Fluent API for constructing inline keyboard menus.

This module provides the main MenuBuilder class that implements the builder pattern
for creating complex, nested inline keyboard menus with ease.
"""

import asyncio
from collections.abc import Sequence
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

        self._items: list[MenuItem] = []
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
        self._items.append(self._create_menu_item(text, handler, params))
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
        self._items.append(MenuItem(text=text, url=url))
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
        # Store submenu reference in params
        params["_submenu_id"] = id(submenu)
        params["_submenu_builder"] = submenu

        return self.add_item(text, handler, **params)

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
        self._navigation.back_button = NavigationButton(text=text, handler=handler, params=params)
        return self

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
        self._navigation.next_button = NavigationButton(text=text, handler=handler, params=params)
        return self

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
        self._navigation.exit_button = NavigationButton(text=text, handler=handler, params=params)
        return self

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
        self._navigation.cancel_button = NavigationButton(text=text, handler=handler, params=params)
        return self

    def build(self) -> InlineKeyboardMarkup:
        """Build the final InlineKeyboardMarkup.

        This method synchronously constructs the menu by encoding all callback data.
        Note: This is a synchronous wrapper around the async build_async method.

        Returns:
            InlineKeyboardMarkup ready to use with python-telegram-bot

        Raises:
            ValidationError: If menu configuration is invalid

        Example:
            >>> menu = builder.build()
            >>> await update.message.reply_text("Choose:", reply_markup=menu)
        """
        # Run async build in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.build_async())

    async def build_async(self) -> InlineKeyboardMarkup:
        """Build the final InlineKeyboardMarkup (async version).

        Returns:
            InlineKeyboardMarkup ready to use

        Raises:
            ValidationError: If menu configuration is invalid
        """
        if not self._items and not self._has_navigation_buttons():
            raise ValidationError("Cannot build empty menu (no items or navigation buttons)")

        # Build keyboard layout
        keyboard: list[list[MenuItem]] = []

        # Arrange items in grid
        current_row: list[MenuItem] = []
        for item in self._items:
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

    def _create_menu_item(self, text: str, handler: str, params: dict[str, Any]) -> MenuItem:
        """Create a MenuItem with encoded callback data (sync version).

        This is a helper that runs the async encoding synchronously.
        """
        try:
            loop = asyncio.get_running_loop()
            # Already in an async context, defer encoding to build time
            return MenuItem(text=text, callback_data="")
        except RuntimeError:
            # No running loop, safe to create new one
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._create_menu_item_async(text, handler, params))

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

