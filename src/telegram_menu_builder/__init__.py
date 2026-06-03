"""
Telegram Menu Builder - A powerful library for creating recursive inline keyboard menus.

This library provides a fluent builder API for creating complex, nested inline keyboard menus
for python-telegram-bot v20+. It handles callback data encoding, storage management, and
provides type-safe menu construction with full IDE support.

Key Features:
    - Builder pattern for intuitive menu construction
    - Intelligent callback data encoding (handles Telegram's 64-byte limit)
    - Hybrid storage strategies (inline, temporary, persistent)
    - Full type safety with Python 3.12+ type hints
    - Unlimited menu nesting with breadcrumb support
    - Async-first design
    - Pluggable storage backends

Example:
    ```python
    from telegram_menu_builder import MenuBuilder

    menu = (MenuBuilder()
        .add_item("Option 1", handler="handle_option1", data={"key": "value"})
        .add_item("Option 2", handler="handle_option2")
        .columns(2)
        .add_back_button()
        .build())
    ```
"""

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

from telegram_menu_builder.builder import MenuBuilder
from telegram_menu_builder.router import MenuRouter
from telegram_menu_builder.storage import (
    MemoryStorage,
    StorageBackend,
)
from telegram_menu_builder.types import (
    CallbackData,
    DecodingError,
    EncodingError,
    LayoutConfig,
    MenuAction,
    MenuBuilderError,
    MenuItem,
    NavigationConfig,
    StorageError,
    StorageStrategy,
    ValidationError,
)

if TYPE_CHECKING:
    from telegram_menu_builder.storage import SQLAlchemyStorage

try:
    __version__ = version("telegram-menu-builder")
except PackageNotFoundError:  # pragma: no cover - only when running from a non-installed tree
    __version__ = "0.0.0+unknown"

__author__ = "Simone Flavio Paris"
__license__ = "MIT"

__all__ = [
    "CallbackData",
    "DecodingError",
    "EncodingError",
    "LayoutConfig",
    "MemoryStorage",
    "MenuAction",
    "MenuBuilder",
    "MenuBuilderError",
    "MenuItem",
    "MenuRouter",
    "NavigationConfig",
    "SQLAlchemyStorage",
    "StorageBackend",
    "StorageError",
    "StorageStrategy",
    "ValidationError",
]


def __getattr__(name: str) -> Any:
    if name == "SQLAlchemyStorage":
        try:
            from telegram_menu_builder.storage import SQLAlchemyStorage
        except ImportError as exc:  # pragma: no cover
            msg = "SQLAlchemyStorage requires the 'sql' extra. Install it with: pip install 'telegram-menu-builder[sql]'"
            raise ImportError(msg) from exc
        return SQLAlchemyStorage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
