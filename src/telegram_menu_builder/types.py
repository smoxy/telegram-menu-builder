"""Core type definitions for the menu builder library.

This module contains all the fundamental data structures used throughout the library,
implemented with Pydantic v2 for validation and type safety.
"""

import json
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from telegram import InlineKeyboardButton


class StorageStrategy(str, Enum):
    """Strategy for storing callback data based on size and persistence requirements.

    Attributes:
        INLINE: Store directly in callback_data (< 60 bytes)
        SHORT: Store in temporary storage with TTL (60-500 bytes)
        PERSISTENT: Store in permanent storage (> 500 bytes or long-lived)
    """

    INLINE = "inline"
    SHORT = "short"
    PERSISTENT = "persistent"


class MenuAction(BaseModel):
    """Represents an action to be executed when a menu item is selected.

    This class handles the encoding and decoding of callback data, intelligently
    choosing the appropriate storage strategy based on data size.

    Attributes:
        handler: Name of the handler function to call
        params: Dictionary of parameters to pass to the handler
        strategy: Storage strategy (auto-selected if None)
        ttl: Time-to-live in seconds for SHORT strategy storage

    Example:
        >>> action = MenuAction(
        ...     handler="edit_user",
        ...     params={"user_id": 123, "field": "email"}
        ... )
    """

    model_config = ConfigDict(frozen=False, arbitrary_types_allowed=True)

    handler: str = Field(..., min_length=1, max_length=100, description="Handler function name")
    params: dict[str, Any] = Field(
        default_factory=dict, description="Parameters to pass to handler"
    )
    strategy: StorageStrategy | None = Field(
        default=None, description="Storage strategy (auto-selected if None)"
    )
    ttl: int = Field(default=3600, ge=60, le=86400, description="TTL in seconds for SHORT strategy")

    @field_validator("handler")
    @classmethod
    def validate_handler_name(cls, v: str) -> str:
        """Validate handler name follows Python identifier rules."""
        if not v.replace("_", "").replace(".", "").isalnum():
            raise ValueError(
                f"Handler name '{v}' must be a valid Python identifier or dot-separated path"
            )
        return v

    @field_validator("params")
    @classmethod
    def validate_params_serializable(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate that params contain only JSON-serializable values."""
        try:
            json.dumps(v)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Params must be JSON-serializable: {e}") from e
        return v


class MenuItem(BaseModel):
    """Represents a single item in an inline keyboard menu.

    Attributes:
        text: Display text for the button
        callback_data: Encoded callback data (max 64 bytes for Telegram)
        url: Optional URL for URL buttons

    Example:
        >>> item = MenuItem(
        ...     text="⚙️ Settings",
        ...     callback_data="encoded_data_here"
        ... )
    """

    model_config = ConfigDict(frozen=True)

    text: str = Field(
        ..., min_length=1, max_length=100, description="Button text displayed to user"
    )
    callback_data: str | None = Field(
        default=None, max_length=64, description="Callback data (Telegram limit: 64 bytes)"
    )
    url: str | None = Field(default=None, description="URL for URL-type buttons")

    @field_validator("callback_data")
    @classmethod
    def validate_callback_size(cls, v: str | None) -> str | None:
        """Ensure callback_data doesn't exceed Telegram's 64-byte limit."""
        if v is not None and len(v.encode("utf-8")) > 64:
            raise ValueError(
                f"callback_data exceeds Telegram's 64-byte limit: {len(v.encode('utf-8'))} bytes"
            )
        return v

    def to_telegram_button(self) -> InlineKeyboardButton:
        """Convert to telegram.InlineKeyboardButton.

        Returns:
            InlineKeyboardButton instance ready for use
        """
        if self.url:
            return InlineKeyboardButton(text=self.text, url=self.url)
        return InlineKeyboardButton(text=self.text, callback_data=self.callback_data or "")


class LayoutConfig(BaseModel):
    """Configuration for menu layout and button arrangement.

    Attributes:
        columns: Number of columns in the grid layout
        max_rows: Maximum number of rows (None for unlimited)
        fill_last_row: Whether to fill the last row or center items
        button_width_balance: Try to balance button widths in same row

    Example:
        >>> layout = LayoutConfig(columns=3, max_rows=5)
    """

    model_config = ConfigDict(frozen=False)

    columns: int = Field(default=3, ge=1, le=8, description="Number of buttons per row")
    max_rows: int | None = Field(
        default=None, ge=1, description="Maximum number of rows (None = unlimited)"
    )
    fill_last_row: bool = Field(default=True, description="Fill last row or center remaining items")
    button_width_balance: bool = Field(
        default=False, description="Try to balance button text widths"
    )


class NavigationButton(BaseModel):
    """Configuration for a navigation button (back, next, exit).

    Attributes:
        text: Button text (emoji + label)
        handler: Handler to call when clicked
        params: Additional parameters for the handler
        position: Where to place the button
    """

    model_config = ConfigDict(frozen=False)

    text: str = Field(..., min_length=1, max_length=50, description="Button text")
    handler: str = Field(..., min_length=1, description="Handler function name")
    params: dict[str, Any] = Field(default_factory=dict, description="Handler parameters")
    position: Literal["top", "bottom", "inline"] = Field(
        default="bottom", description="Button position in menu"
    )


class NavigationConfig(BaseModel):
    """Configuration for navigation buttons (back, next, exit).

    Attributes:
        back_button: Back button configuration
        next_button: Next button configuration
        exit_button: Exit button configuration
        cancel_button: Cancel button configuration

    Example:
        >>> nav = NavigationConfig(
        ...     back_button=NavigationButton(
        ...         text="🔙 Back",
        ...         handler="go_back"
        ...     )
        ... )
    """

    model_config = ConfigDict(frozen=False)

    back_button: NavigationButton | None = Field(
        default=None, description="Back button configuration"
    )
    next_button: NavigationButton | None = Field(
        default=None, description="Next button configuration"
    )
    exit_button: NavigationButton | None = Field(
        default=None, description="Exit/Close button configuration"
    )
    cancel_button: NavigationButton | None = Field(
        default=None, description="Cancel button configuration"
    )

    @model_validator(mode="after")
    def validate_exclusive_buttons(self) -> "NavigationConfig":
        """Ensure exit and cancel buttons are not used together."""
        if self.exit_button is not None and self.cancel_button is not None:
            raise ValueError("Cannot have both exit_button and cancel_button")
        return self


class CallbackData(BaseModel):
    """Complete callback data structure for menu interactions.

    This is the internal representation of all data associated with a callback.
    It gets encoded into the callback_data string or stored externally.

    Attributes:
        action: The menu action to execute
        menu_id: Unique identifier for the menu instance
        timestamp: When the callback data was created
        metadata: Additional metadata (breadcrumb, context, etc.)

    Example:
        >>> callback = CallbackData(
        ...     action=MenuAction(handler="test", params={"id": 1}),
        ...     menu_id="main_menu"
        ... )
    """

    model_config = ConfigDict(frozen=False)

    action: MenuAction = Field(..., description="Action to execute")
    menu_id: str | None = Field(default=None, max_length=50, description="Menu identifier")
    timestamp: float | None = Field(default=None, description="Creation timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# Type aliases for handler functions
HandlerFunc = Callable[[Any, Any, dict[str, Any]], Awaitable[None]]
"""Type alias for async handler functions.

Args:
    update: Telegram Update object
    context: Telegram Context object
    params: Decoded parameters from callback data
"""


class MenuBuilderError(Exception):
    """Base exception for menu builder errors."""


class EncodingError(MenuBuilderError):
    """Raised when callback data encoding fails."""


class DecodingError(MenuBuilderError):
    """Raised when callback data decoding fails."""


class StorageError(MenuBuilderError):
    """Raised when storage operations fail."""


class ValidationError(MenuBuilderError):
    """Raised when menu validation fails."""
