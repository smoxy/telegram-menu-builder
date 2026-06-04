"""Test suite for application-free, budget-enforced static menu building (Feature A).

These tests exercise the synchronous, storage-free build surface of MenuBuilder:
``to_markup()`` (returns a ``telegram.InlineKeyboardMarkup`` with no event loop),
``to_raw()`` (returns a plain Telegram Bot API dict), ``assert_inline()`` (a cheap
pre-flight), and the ``on_oversize`` budget policy. Any item that would need a storage
spill must raise ``EncodingError`` on these sync paths instead of silently spilling.
"""

import pytest
from telegram import InlineKeyboardMarkup

from telegram_menu_builder import MenuBuilder
from telegram_menu_builder.encoding import CallbackEncoder
from telegram_menu_builder.storage import MemoryStorage
from telegram_menu_builder.types import EncodingError


class TestToMarkup:
    """Tests for the synchronous, storage-free ``to_markup()`` builder method."""

    @pytest.fixture
    def storage(self):
        """Provide a fresh storage instance for each test."""
        return MemoryStorage()

    @pytest.fixture
    def builder(self, storage):
        """Provide a fresh builder instance for each test."""
        return MenuBuilder(storage=storage)

    def test_to_markup_is_sync_and_returns_markup(self, builder):
        """to_markup() is callable from a plain def (no event loop) and returns markup."""
        markup = (
            builder.add_item("Item 1", handler="handler1", id=1)
            .add_item("Item 2", handler="handler2", id=2)
            .columns(2)
            .to_markup()
        )

        assert isinstance(markup, InlineKeyboardMarkup)
        assert len(markup.inline_keyboard) == 1
        assert len(markup.inline_keyboard[0]) == 2

    def test_to_markup_buttons_are_inline(self, builder):
        """Every callback button rendered by to_markup() is an inline (I:/IC:) ref."""
        markup = (
            builder.add_item("Item 1", handler="handler1", id=1)
            .add_item("Item 2", handler="handler2", id=2)
            .to_markup()
        )

        for row in markup.inline_keyboard:
            for button in row:
                assert button.callback_data is not None
                assert button.callback_data.startswith(("I:", "IC:"))

    def test_to_markup_url_button_renders(self, builder):
        """URL buttons render through to_markup() without callback data."""
        markup = builder.add_url_button("Site", "https://example.com").to_markup()

        button = markup.inline_keyboard[0][0]
        assert button.url == "https://example.com"
        assert button.callback_data is None

    def test_to_markup_with_navigation_and_submenu(self, storage):
        """Navigation buttons and a submenu still render through to_markup()."""
        submenu = MenuBuilder(storage=storage).add_item("Sub", handler="sub_handler")
        builder = (
            MenuBuilder(storage=storage)
            .add_item("Item", handler="handler1")
            .add_submenu("Open", submenu)
            .add_back_button()
            .add_exit_button()
        )

        markup = builder.to_markup()

        # 2 item rows (item + submenu at default columns leaves them grouped), plus
        # a back-button row and an exit-button row.
        flat = [button for row in markup.inline_keyboard for button in row]
        texts = [button.text for button in flat]
        assert "Open" in texts
        assert any("Back" in text for text in texts)
        assert any("Exit" in text for text in texts)
        # All callback buttons are inline.
        for button in flat:
            if button.url is None:
                assert button.callback_data is not None
                assert button.callback_data.startswith(("I:", "IC:"))

    async def test_to_markup_round_trips_through_encoder(self, storage):
        """A to_markup() button's callback_data decodes back to the original action."""
        builder = MenuBuilder(storage=storage)
        builder.add_item("Edit", handler="edit_user", user_id=99, field="email")

        markup = builder.to_markup()
        callback_data = markup.inline_keyboard[0][0].callback_data

        assert callback_data is not None
        action = await CallbackEncoder(storage).decode(callback_data)
        assert action.handler == "edit_user"
        assert action.params == {"user_id": 99, "field": "email"}

    def test_to_markup_oversize_raises(self, builder):
        """An item too large to fit inline makes to_markup() raise EncodingError."""
        builder.add_item("Big", handler="big_handler", blob="x" * 500)

        with pytest.raises(EncodingError):
            builder.to_markup()


class TestToRaw:
    """Tests for the synchronous, storage-free ``to_raw()`` builder method."""

    @pytest.fixture
    def storage(self):
        """Provide a fresh storage instance for each test."""
        return MemoryStorage()

    @pytest.fixture
    def builder(self, storage):
        """Provide a fresh builder instance for each test."""
        return MenuBuilder(storage=storage)

    def test_to_raw_shape(self, builder):
        """to_raw() returns a plain Bot API dict with the right top-level shape."""
        raw = builder.add_item("Item", handler="handler1").to_raw()

        assert isinstance(raw, dict)
        assert "inline_keyboard" in raw
        assert isinstance(raw["inline_keyboard"], list)
        assert isinstance(raw["inline_keyboard"][0], list)

    def test_to_raw_button_dicts(self, builder):
        """Callback buttons emit {text, callback_data}; url buttons emit {text, url}."""
        raw = (
            builder.add_item("Callback", handler="handler1", id=1)
            .add_url_button("Link", "https://example.com")
            .columns(1)
            .to_raw()
        )

        flat = [button for row in raw["inline_keyboard"] for button in row]

        callback_button = next(b for b in flat if "callback_data" in b)
        assert callback_button["text"] == "Callback"
        assert callback_button["callback_data"].startswith(("I:", "IC:"))
        assert "url" not in callback_button

        url_button = next(b for b in flat if "url" in b)
        assert url_button == {"text": "Link", "url": "https://example.com"}
        assert "callback_data" not in url_button

    def test_to_raw_with_navigation_and_submenu(self, storage):
        """Navigation buttons and a submenu still render through to_raw()."""
        submenu = MenuBuilder(storage=storage).add_item("Sub", handler="sub_handler")
        raw = (
            MenuBuilder(storage=storage)
            .add_item("Item", handler="handler1")
            .add_submenu("Open", submenu)
            .add_back_button()
            .to_raw()
        )

        flat = [button for row in raw["inline_keyboard"] for button in row]
        texts = [button["text"] for button in flat]
        assert "Open" in texts
        assert any("Back" in text for text in texts)
        for button in flat:
            assert "callback_data" in button
            assert button["callback_data"].startswith(("I:", "IC:"))

    def test_to_raw_oversize_raises(self, builder):
        """An item too large to fit inline makes to_raw() raise EncodingError."""
        builder.add_item("Big", handler="big_handler", blob="x" * 500)

        with pytest.raises(EncodingError):
            builder.to_raw()


class TestAssertInline:
    """Tests for the ``assert_inline()`` pre-flight on MenuBuilder."""

    @pytest.fixture
    def storage(self):
        """Provide a fresh storage instance for each test."""
        return MemoryStorage()

    def test_assert_inline_passes_for_small_menu(self, storage):
        """assert_inline() returns None (no raise) when every item fits inline."""
        builder = (
            MenuBuilder(storage=storage)
            .add_item("Item 1", handler="handler1", id=1)
            .add_item("Item 2", handler="handler2", id=2)
            .add_back_button()
        )

        assert builder.assert_inline() is None

    def test_assert_inline_raises_for_oversize_item(self, storage):
        """assert_inline() raises EncodingError when an item would need storage."""
        builder = MenuBuilder(storage=storage).add_item(
            "Big", handler="big_handler", blob="x" * 500
        )

        with pytest.raises(EncodingError):
            builder.assert_inline()


class TestOnOversizePolicy:
    """Tests for the ``on_oversize`` build-time budget policy."""

    @pytest.fixture
    def storage(self):
        """Provide a fresh storage instance for each test."""
        return MemoryStorage()

    async def test_default_spills_on_oversize(self, storage):
        """The default builder (on_oversize='spill') spills oversize items to storage."""
        builder = MenuBuilder(storage=storage)
        builder.add_item("Big", handler="big_handler", blob="x" * 500)

        menu = await builder.build_async()
        callback_data = menu.inline_keyboard[0][0].callback_data

        assert callback_data is not None
        assert callback_data.startswith(("S:", "P:"))

    async def test_error_policy_raises_on_oversize(self, storage):
        """on_oversize='error' makes build_async raise instead of spilling."""
        builder = MenuBuilder(storage=storage, on_oversize="error")
        builder.add_item("Big", handler="big_handler", blob="x" * 500)

        with pytest.raises(EncodingError):
            await builder.build_async()

    async def test_error_policy_builds_small_menu(self, storage):
        """on_oversize='error' still builds menus whose items fit inline."""
        builder = MenuBuilder(storage=storage, on_oversize="error")
        builder.add_item("Item", handler="handler1", id=1)

        menu = await builder.build_async()
        callback_data = menu.inline_keyboard[0][0].callback_data

        assert callback_data is not None
        assert callback_data.startswith(("I:", "IC:"))
