"""Storage backend implementations for callback data persistence."""

from telegram_menu_builder.storage.base import StorageBackend
from telegram_menu_builder.storage.memory import MemoryStorage

__all__ = [
    "MemoryStorage",
    "StorageBackend",
]
