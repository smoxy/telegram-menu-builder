"""Test suite for the testing helpers module (Feature C).

These tests exercise ``telegram_menu_builder.testing``: ``simulate_tap`` (drives a
router with a fabricated callback Update built from stdlib mocks), the ``tap``
convenience (encodes a handler+params then simulates), the ``TapResult`` record, and
``assert_inline`` (verifies every button is an inline callback ref, not a storage ref).
"""

import pytest

from telegram_menu_builder import MenuBuilder, MenuRouter
from telegram_menu_builder.storage import MemoryStorage
from telegram_menu_builder.testing import TapResult, assert_inline, simulate_tap, tap
from telegram_menu_builder.types import MenuAction


class TestSimulateTap:
    """Tests for simulate_tap driving a router via a fabricated Update."""

    @pytest.fixture
    def storage(self):
        """Provide a fresh storage instance for each test."""
        return MemoryStorage()

    @pytest.fixture
    def router(self, storage):
        """Provide a router sharing the storage so encode/decode round-trips."""
        return MenuRouter(storage=storage)

    async def test_simulate_tap_drives_handler(self, router):
        """simulate_tap awaits the matching handler with the decoded params."""
        received = {}

        @router.handler("greet")
        async def greet(update, ctx, params):
            received.update(params)

        encoded = await router.encoder.encode(MenuAction(handler="greet", params={"user_id": 7}))
        result = await simulate_tap(router, encoded)

        assert received == {"user_id": 7}
        assert isinstance(result, TapResult)

    async def test_simulate_tap_reports_answered(self, router):
        """simulate_tap reflects that the router auto-answered the callback query."""

        @router.handler("noop")
        async def noop(update, ctx, params):
            pass

        encoded = await router.encoder.encode(MenuAction(handler="noop", params={}))
        result = await simulate_tap(router, encoded)

        assert result.answered is True
        assert result.handler_error is None

    async def test_simulate_tap_reports_edited_text(self, router):
        """simulate_tap captures the text a handler edits the message to."""

        @router.handler("show")
        async def show(update, ctx, params):
            await update.callback_query.edit_message_text("Hello world")

        encoded = await router.encoder.encode(MenuAction(handler="show", params={}))
        result = await simulate_tap(router, encoded)

        assert result.edited_text == "Hello world"

    async def test_simulate_tap_passes_user_id(self, router):
        """simulate_tap exposes the given user_id on update.effective_user."""
        seen = {}

        @router.handler("whoami")
        async def whoami(update, ctx, params):
            seen["user_id"] = update.effective_user.id

        encoded = await router.encoder.encode(MenuAction(handler="whoami", params={}))
        await simulate_tap(router, encoded, user_id=4242)

        assert seen["user_id"] == 4242


class TestTap:
    """Tests for the tap() convenience wrapper."""

    @pytest.fixture
    def router(self):
        """Provide a fresh router."""
        return MenuRouter(storage=MemoryStorage())

    async def test_tap_encodes_and_drives_handler(self, router):
        """tap(router, 'h', x=1) encodes handler+params then drives the handler."""
        received = {}

        @router.handler("h")
        async def h(update, ctx, params):
            received.update(params)

        result = await tap(router, "h", x=1)

        assert received == {"x": 1}
        assert isinstance(result, TapResult)
        assert result.answered is True


class TestAssertInline:
    """Tests for the assert_inline() testing helper."""

    @pytest.fixture
    def storage(self):
        """Provide a fresh storage instance for each test."""
        return MemoryStorage()

    def test_assert_inline_passes_on_inline_builder(self, storage):
        """assert_inline accepts a MenuBuilder whose items all fit inline."""
        builder = (
            MenuBuilder(storage=storage)
            .add_item("Item 1", handler="handler1", id=1)
            .add_item("Item 2", handler="handler2", id=2)
        )

        assert assert_inline(builder) is None

    async def test_assert_inline_passes_on_inline_markup(self, storage):
        """assert_inline accepts an InlineKeyboardMarkup with only inline refs."""
        builder = MenuBuilder(storage=storage).add_item("Item", handler="handler1", id=1)
        markup = await builder.build_async()

        assert assert_inline(markup) is None

    async def test_assert_inline_raises_on_spilled_markup(self, storage):
        """assert_inline raises AssertionError on a built menu that spilled to storage."""
        builder = MenuBuilder(storage=storage)
        builder.add_item("Big", handler="big_handler", blob="x" * 500)
        markup = await builder.build_async()

        # The oversize item spilled to storage (S:/P:), so this is not inline.
        assert markup.inline_keyboard[0][0].callback_data.startswith(("S:", "P:"))

        with pytest.raises(AssertionError):
            assert_inline(markup)

    def test_assert_inline_accepts_raw_dict(self, storage):
        """assert_inline accepts a raw Bot API dict and verifies inline callback refs."""
        builder = MenuBuilder(storage=storage).add_item("Item", handler="handler1", id=1)
        raw = builder.to_raw()

        assert assert_inline(raw) is None
