"""Tests for package-level metadata and public API surface."""

from importlib.metadata import version

import telegram_menu_builder as tmb
from telegram_menu_builder import (
    DecodingError,
    EncodingError,
    MenuBuilderError,
    StorageError,
    ValidationError,
)


def test_version_matches_installed_metadata():
    """__version__ is single-sourced from the installed package metadata."""
    assert tmb.__version__ == version("telegram-menu-builder")
    assert tmb.__version__  # non-empty


def test_exception_hierarchy_exported():
    """All library exceptions are exported and subclass MenuBuilderError."""
    exported = {
        "MenuBuilderError",
        "EncodingError",
        "DecodingError",
        "StorageError",
        "ValidationError",
    }
    assert exported <= set(tmb.__all__)

    for exc in (EncodingError, DecodingError, StorageError, ValidationError):
        assert issubclass(exc, MenuBuilderError)
    assert issubclass(MenuBuilderError, Exception)


def test_all_names_are_importable():
    """Everything advertised in __all__ is importable from the package.

    The CI and publish environments install every optional extra (``[sql]``,
    ``[redis]``), so the lazy storage-backend exports resolve here exactly like the
    eager names — a dangling or misspelled entry in ``__all__`` fails this test.
    """
    for name in tmb.__all__:
        assert getattr(tmb, name) is not None, f"{name} listed in __all__ but not importable"
