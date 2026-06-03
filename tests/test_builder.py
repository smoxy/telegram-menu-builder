"""Test suite for MenuBuilder class.

These tests demonstrate how to use pytest to test menu construction.
"""

import pytest
from telegram import InlineKeyboardMarkup

from telegram_menu_builder import MenuBuilder
from telegram_menu_builder.encoding import CallbackEncoder
from telegram_menu_builder.storage import MemoryStorage
from telegram_menu_builder.types import ValidationError


class TestMenuBuilder:
    """Tests for MenuBuilder class."""

    @pytest.fixture
    def storage(self):
        """Provide a fresh storage instance for each test."""
        return MemoryStorage()

    @pytest.fixture
    def builder(self, storage):
        """Provide a fresh builder instance for each test."""
        return MenuBuilder(storage=storage)

    def test_empty_menu_with_navigation_builds(self, builder):
        """Test that a menu with only navigation buttons can be built."""
        menu = builder.add_back_button().build()

        assert isinstance(menu, InlineKeyboardMarkup)
        assert len(menu.inline_keyboard) == 1
        assert len(menu.inline_keyboard[0]) == 1

    def test_empty_menu_raises_error(self, builder):
        """Test that building an empty menu raises ValidationError."""
        with pytest.raises(ValidationError, match="empty menu"):
            builder.build()

    def test_add_single_item(self, builder):
        """Test adding a single menu item."""
        menu = builder.add_item("Test", handler="test_handler").build()

        assert isinstance(menu, InlineKeyboardMarkup)
        assert len(menu.inline_keyboard) == 1
        assert menu.inline_keyboard[0][0].text == "Test"

    def test_add_multiple_items(self, builder):
        """Test adding multiple menu items."""
        menu = (
            builder.add_item("Item 1", handler="handler1")
            .add_item("Item 2", handler="handler2")
            .add_item("Item 3", handler="handler3")
            .columns(2)
            .build()
        )

        # Should have 2 rows (2 columns, 3 items)
        assert len(menu.inline_keyboard) == 2
        assert len(menu.inline_keyboard[0]) == 2  # First row: 2 items
        assert len(menu.inline_keyboard[1]) == 1  # Second row: 1 item

    def test_add_items_batch(self, builder):
        """Test adding multiple items at once."""
        items = [
            ("Item 1", "handler1", {"id": 1}),
            ("Item 2", "handler2", {"id": 2}),
        ]

        menu = builder.add_items(items).columns(1).build()

        assert len(menu.inline_keyboard) == 2

    def test_add_url_button(self, builder):
        """Test adding a URL button."""
        menu = builder.add_url_button("Google", "https://google.com").build()

        assert len(menu.inline_keyboard) == 1
        assert menu.inline_keyboard[0][0].url == "https://google.com"

    def test_columns_configuration(self, builder):
        """Test configuring columns."""
        menu = (
            builder.add_item("1", handler="h1")
            .add_item("2", handler="h2")
            .add_item("3", handler="h3")
            .add_item("4", handler="h4")
            .columns(3)
            .build()
        )

        # Should have 2 rows (3 columns, 4 items)
        assert len(menu.inline_keyboard) == 2
        assert len(menu.inline_keyboard[0]) == 3
        assert len(menu.inline_keyboard[1]) == 1

    def test_invalid_columns_raises_error(self, builder):
        """Test that invalid column count raises error."""
        with pytest.raises(ValidationError):
            builder.columns(0)

        with pytest.raises(ValidationError):
            builder.columns(9)

    def test_max_rows_limit(self, builder):
        """Test max_rows limitation."""
        builder_with_many_items = builder
        for i in range(10):
            builder_with_many_items.add_item(f"Item {i}", handler=f"h{i}")

        menu = builder_with_many_items.columns(2).max_rows(3).build()

        # Should have max 3 rows of items + navigation
        assert len(menu.inline_keyboard) <= 3

    def test_back_button(self, builder):
        """Test adding back button."""
        menu = (
            builder.add_item("Item", handler="test")
            .add_back_button(handler="go_back", page=1)
            .build()
        )

        # Should have 2 rows: 1 for item, 1 for back button
        assert len(menu.inline_keyboard) == 2
        assert "Back" in menu.inline_keyboard[1][0].text

    def test_navigation_buttons_same_row(self, builder):
        """Test that back and next buttons appear on same row."""
        menu = builder.add_item("Item", handler="test").add_back_button().add_next_button().build()

        # Last row should have 2 buttons (back and next)
        assert len(menu.inline_keyboard[-1]) == 2

    def test_exit_button_separate_row(self, builder):
        """Test that exit button appears on separate row."""
        menu = builder.add_item("Item", handler="test").add_exit_button().build()

        # Should have 2 rows
        assert len(menu.inline_keyboard) == 2
        # Last row should have 1 button
        assert len(menu.inline_keyboard[-1]) == 1

    def test_item_with_complex_parameters(self, builder):
        """Test adding item with complex parameters."""
        menu = builder.add_item(
            "Edit User",
            handler="edit_user",
            user_id=123,
            field="email",
            metadata={"source": "admin_panel"},
            breadcrumb=["main", "users", "edit"],
        ).build()

        assert len(menu.inline_keyboard) == 1
        # Parameters are encoded in callback_data
        assert menu.inline_keyboard[0][0].callback_data is not None

    async def test_build_async_encodes_callback_data(self, storage):
        """build_async produces non-empty, decodable callback data.

        Regression test for the bug where items added via add_item lost their
        handler and params (empty callback_data) when built inside a running loop.
        """
        builder = MenuBuilder(storage=storage)
        builder.add_item("Greet", handler="greet", user_id=42)

        menu = await builder.build_async()
        callback_data = menu.inline_keyboard[0][0].callback_data

        assert callback_data  # non-empty
        action = await CallbackEncoder(storage).decode(callback_data)
        assert action.handler == "greet"
        assert action.params == {"user_id": 42}

    async def test_sync_build_inside_running_loop(self, storage):
        """Sync .build() called inside a running loop still encodes callback data.

        Exercises the worker-thread fallback path in build().
        """
        builder = MenuBuilder(storage=storage)
        builder.add_item("Greet", handler="greet", user_id=7)

        menu = builder.build()
        callback_data = menu.inline_keyboard[0][0].callback_data

        assert callback_data
        action = await CallbackEncoder(storage).decode(callback_data)
        assert action.handler == "greet"
        assert action.params == {"user_id": 7}

    async def test_submenu_builds_without_serialization_error(self, storage):
        """add_submenu encodes successfully (the builder object is not serialized)."""
        submenu = MenuBuilder(storage=storage).add_item("Sub", handler="sub_handler")
        builder = MenuBuilder(storage=storage).add_submenu("Open", submenu)

        menu = await builder.build_async()
        callback_data = menu.inline_keyboard[0][0].callback_data

        assert callback_data
        action = await CallbackEncoder(storage).decode(callback_data)
        assert action.params["_submenu_id"] == id(submenu)
        assert builder.get_submenu(id(submenu)) is submenu

    def test_fluent_api_chaining(self, builder):
        """Test that all methods return self for chaining."""
        result = (
            builder.add_item("1", handler="h1")
            .add_item("2", handler="h2")
            .columns(2)
            .max_rows(5)
            .add_back_button()
            .add_next_button()
        )

        assert result is builder
