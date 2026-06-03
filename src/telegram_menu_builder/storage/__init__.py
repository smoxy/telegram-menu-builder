"""Storage backend implementations for callback data persistence."""

from typing import TYPE_CHECKING, Any

from telegram_menu_builder.storage.base import StorageBackend
from telegram_menu_builder.storage.memory import MemoryStorage

if TYPE_CHECKING:
    from telegram_menu_builder.storage.redis import RedisStorage
    from telegram_menu_builder.storage.sqlalchemy import SQLAlchemyStorage

__all__ = [
    "MemoryStorage",
    "RedisStorage",
    "SQLAlchemyStorage",
    "StorageBackend",
]


def __getattr__(name: str) -> Any:
    if name == "RedisStorage":
        try:
            from telegram_menu_builder.storage.redis import RedisStorage
        except ImportError as exc:  # pragma: no cover
            msg = "RedisStorage requires the 'redis' extra. Install it with: pip install 'telegram-menu-builder[redis]'"
            raise ImportError(msg) from exc
        return RedisStorage
    if name == "SQLAlchemyStorage":
        try:
            from telegram_menu_builder.storage.sqlalchemy import SQLAlchemyStorage
        except ImportError as exc:  # pragma: no cover
            msg = "SQLAlchemyStorage requires the 'sql' extra. Install it with: pip install 'telegram-menu-builder[sql]'"
            raise ImportError(msg) from exc
        return SQLAlchemyStorage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
