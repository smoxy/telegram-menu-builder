"""Test suite for the Pydantic models and validators in types.py."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from telegram_menu_builder.types import (
    CallbackData,
    LayoutConfig,
    MenuAction,
    MenuItem,
    NavigationButton,
    NavigationConfig,
    StorageStrategy,
)


class TestMenuAction:
    """Tests for MenuAction validation."""

    def test_valid_handler_names(self):
        """Alphanumeric, underscore and dotted handler names are accepted."""
        assert MenuAction(handler="edit_user").handler == "edit_user"
        assert MenuAction(handler="users.edit").handler == "users.edit"

    def test_invalid_handler_name_rejected(self):
        """Handler names with illegal characters are rejected."""
        with pytest.raises(PydanticValidationError):
            MenuAction(handler="bad name!")

    def test_params_must_be_json_serializable(self):
        """Non-serializable params raise a validation error."""
        with pytest.raises(PydanticValidationError):
            MenuAction(handler="h", params={"obj": object()})

    def test_ttl_bounds(self):
        """ttl is bounded to [60, 86400]."""
        assert MenuAction(handler="h", ttl=60).ttl == 60
        with pytest.raises(PydanticValidationError):
            MenuAction(handler="h", ttl=59)
        with pytest.raises(PydanticValidationError):
            MenuAction(handler="h", ttl=86401)


class TestMenuItem:
    """Tests for MenuItem validation and conversion."""

    def test_callback_within_limit(self):
        """Callback data up to 64 bytes is accepted."""
        item = MenuItem(text="ok", callback_data="x" * 64)
        assert item.callback_data == "x" * 64

    def test_callback_over_limit_rejected(self):
        """Callback data over 64 bytes is rejected."""
        with pytest.raises(PydanticValidationError):
            MenuItem(text="ok", callback_data="x" * 65)

    def test_callback_size_counts_utf8_bytes(self):
        """Multi-byte characters count by their UTF-8 byte length."""
        # Each rocket emoji is 4 UTF-8 bytes; 17 * 4 = 68 > 64.
        with pytest.raises(PydanticValidationError):
            MenuItem(text="ok", callback_data="🚀" * 17)

    def test_item_is_frozen(self):
        """MenuItem instances are immutable."""
        item = MenuItem(text="ok", callback_data="data")
        with pytest.raises(PydanticValidationError):
            item.text = "changed"

    def test_to_telegram_button_callback(self):
        """A callback item converts to a callback button."""
        button = MenuItem(text="Go", callback_data="data").to_telegram_button()
        assert button.text == "Go"
        assert button.callback_data == "data"
        assert button.url is None

    def test_to_telegram_button_url(self):
        """A URL item converts to a URL button."""
        button = MenuItem(text="Site", url="https://example.com").to_telegram_button()
        assert button.url == "https://example.com"

    def test_to_telegram_button_empty_callback(self):
        """A missing callback falls back to an empty string."""
        button = MenuItem(text="x").to_telegram_button()
        assert button.callback_data == ""


class TestLayoutConfig:
    """Tests for LayoutConfig bounds."""

    def test_defaults(self):
        """Defaults are sensible."""
        layout = LayoutConfig()
        assert layout.columns == 3
        assert layout.max_rows is None

    def test_columns_bounds(self):
        """columns must be within 1..8."""
        with pytest.raises(PydanticValidationError):
            LayoutConfig(columns=0)
        with pytest.raises(PydanticValidationError):
            LayoutConfig(columns=9)

    def test_max_rows_bound(self):
        """max_rows must be >= 1 when set."""
        with pytest.raises(PydanticValidationError):
            LayoutConfig(max_rows=0)


class TestNavigationConfig:
    """Tests for NavigationConfig exclusivity rule."""

    def test_exit_and_cancel_mutually_exclusive(self):
        """Configuring both an exit and a cancel button is rejected."""
        with pytest.raises(PydanticValidationError, match="exit_button and cancel_button"):
            NavigationConfig(
                exit_button=NavigationButton(text="Exit", handler="exit"),
                cancel_button=NavigationButton(text="Cancel", handler="cancel"),
            )

    def test_single_button_ok(self):
        """A single navigation button is fine."""
        config = NavigationConfig(back_button=NavigationButton(text="Back", handler="go_back"))
        assert config.back_button is not None


class TestStorageStrategy:
    """Tests for the StorageStrategy enum."""

    def test_is_string_enum(self):
        """StorageStrategy members compare equal to their string values."""
        assert StorageStrategy.INLINE == "inline"
        assert StorageStrategy.SHORT == "short"
        assert StorageStrategy.PERSISTENT == "persistent"


class TestCallbackData:
    """Tests for the CallbackData wrapper model."""

    def test_defaults(self):
        """CallbackData wraps an action with optional metadata."""
        data = CallbackData(action=MenuAction(handler="h", params={"id": 1}))
        assert data.action.handler == "h"
        assert data.menu_id is None
        assert data.metadata == {}
