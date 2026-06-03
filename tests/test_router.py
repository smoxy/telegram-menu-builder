"""Test suite for MenuRouter and RouterGroup.

These tests use lightweight mocks for the Telegram Update/CallbackQuery objects so
that routing, middleware, and error handling can be exercised without a live bot.
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from telegram_menu_builder import MenuBuilder, MenuRouter
from telegram_menu_builder.encoding import CallbackEncoder
from telegram_menu_builder.router import RouterGroup
from telegram_menu_builder.storage import MemoryStorage
from telegram_menu_builder.types import MenuAction


def make_update(data):
    """Build a fake Update whose callback_query carries the given data."""
    callback_query = MagicMock()
    callback_query.data = data
    callback_query.answer = AsyncMock()
    update = MagicMock()
    update.callback_query = callback_query
    return update


class TestMenuRouter:
    """Tests for the MenuRouter dispatch logic."""

    @pytest.fixture
    def storage(self):
        """Provide a fresh storage instance for each test."""
        return MemoryStorage()

    @pytest.fixture
    def router(self, storage):
        """Provide a router sharing the storage so encode/decode round-trips."""
        return MenuRouter(storage=storage)

    @pytest.fixture
    def context(self):
        """Provide a fake Telegram context."""
        return MagicMock()

    async def _encode(self, router, handler, params):
        return await router.encoder.encode(MenuAction(handler=handler, params=params))

    async def test_routes_to_registered_handler(self, router, context):
        """A decoded action is dispatched to the matching handler with its params."""
        handler = AsyncMock()
        router.register_handler("greet", handler)

        encoded = await self._encode(router, "greet", {"user_id": 7})
        update = make_update(encoded)

        await router.route(update, context)

        handler.assert_awaited_once_with(update, context, {"user_id": 7})
        update.callback_query.answer.assert_awaited_once_with()

    async def test_handler_decorator_registers(self, router, context):
        """The @router.handler decorator registers the function."""
        seen = {}

        @router.handler("pick")
        async def pick(update, ctx, params):
            seen.update(params)

        assert "pick" in router.list_handlers()
        encoded = await self._encode(router, "pick", {"id": 1})
        await router.route(make_update(encoded), context)
        assert seen == {"id": 1}

    async def test_middleware_runs_in_order(self, router, context):
        """before -> handler -> after middleware execute in sequence."""
        calls = []

        @router.before
        async def before(update, ctx, params):
            calls.append("before")

        async def handler(update, ctx, params):
            calls.append("handler")

        router.register_handler("h", handler)

        @router.after
        async def after(update, ctx, params):
            calls.append("after")

        encoded = await self._encode(router, "h", {})
        await router.route(make_update(encoded), context)

        assert calls == ["before", "handler", "after"]

    async def test_unknown_handler_without_default(self, router, context):
        """Unknown handler and no default -> answers 'Action not available'."""
        encoded = await self._encode(router, "missing", {})
        update = make_update(encoded)

        await router.route(update, context)

        update.callback_query.answer.assert_awaited_once_with("Action not available")

    async def test_unknown_handler_uses_default(self, storage, context):
        """Unknown handler falls back to the default handler when configured."""
        default = AsyncMock()
        router = MenuRouter(storage=storage, default_handler=default)

        encoded = await self._encode(router, "missing", {"a": 1})
        update = make_update(encoded)

        await router.route(update, context)

        default.assert_awaited_once_with(update, context, {"a": 1})
        update.callback_query.answer.assert_awaited_once_with()

    async def test_decoding_error_triggers_error_handler(self, router, context):
        """Invalid callback data triggers error handlers and an error answer."""
        error_handler = AsyncMock()
        router.on_error(error_handler)

        update = make_update("THIS_IS_NOT_VALID")
        await router.route(update, context)

        error_handler.assert_awaited_once()
        update.callback_query.answer.assert_awaited_once_with("Invalid or expired action")

    async def test_handler_exception_triggers_error_handler(self, router, context):
        """An exception raised inside a handler is caught and reported."""
        error_handler = AsyncMock()
        router.on_error(error_handler)

        async def boom(update, ctx, params):
            raise RuntimeError("kaboom")

        router.register_handler("boom", boom)

        encoded = await self._encode(router, "boom", {})
        update = make_update(encoded)

        await router.route(update, context)

        error_handler.assert_awaited_once()
        update.callback_query.answer.assert_awaited_once_with("An error occurred")

    async def test_auto_answer_disabled(self, storage, context):
        """With auto_answer=False the router never answers the callback query."""
        router = MenuRouter(storage=storage, auto_answer=False)
        handler = AsyncMock()
        router.register_handler("h", handler)

        encoded = await self._encode(router, "h", {})
        update = make_update(encoded)

        await router.route(update, context)

        handler.assert_awaited_once()
        update.callback_query.answer.assert_not_awaited()

    async def test_no_callback_query_is_ignored(self, router, context):
        """An update without a callback_query is ignored without error."""
        update = MagicMock()
        update.callback_query = None
        await router.route(update, context)  # should not raise

    async def test_empty_data_is_answered(self, router, context):
        """A callback query with no data is answered and skipped."""
        update = make_update(None)
        await router.route(update, context)
        update.callback_query.answer.assert_awaited_once_with()

    def test_register_handlers_bulk_and_overwrite_warns(self, router, caplog):
        """register_handlers adds many; re-registering warns."""

        async def a(update, ctx, params):
            pass

        router.register_handlers({"x": a, "y": a})
        assert set(router.list_handlers()) == {"x", "y"}

        with caplog.at_level(logging.WARNING):
            router.register_handler("x", a)
        assert any("Overwriting" in record.message for record in caplog.records)

    def test_unregister_and_get_handler(self, router):
        """unregister returns True/False; get_handler returns the function or None."""

        async def a(update, ctx, params):
            pass

        router.register_handler("x", a)
        assert router.get_handler("x") is a
        assert router.unregister_handler("x") is True
        assert router.unregister_handler("x") is False
        assert router.get_handler("x") is None

    async def test_set_default_handler(self, router, context):
        """set_default_handler installs a fallback used for unknown actions."""
        default = AsyncMock()
        router.set_default_handler(default)

        encoded = await self._encode(router, "unknown", {"k": 1})
        update = make_update(encoded)
        await router.route(update, context)

        default.assert_awaited_once_with(update, context, {"k": 1})

    def test_properties_expose_storage_and_encoder(self, storage):
        """The storage and encoder properties return the configured instances."""
        router = MenuRouter(storage=storage)
        assert router.storage is storage
        assert isinstance(router.encoder, CallbackEncoder)

    async def test_build_then_route_round_trip(self, storage, context):
        """A menu built with MenuBuilder routes back to the original handler+params."""
        builder = MenuBuilder(storage=storage)
        builder.add_item("Edit", handler="edit_user", user_id=99, field="email")
        menu = await builder.build_async()
        callback_data = menu.inline_keyboard[0][0].callback_data

        router = MenuRouter(storage=storage)
        received = {}

        async def edit_user(update, ctx, params):
            received.update(params)

        router.register_handler("edit_user", edit_user)
        await router.route(make_update(callback_data), context)

        assert received == {"user_id": 99, "field": "email"}


class TestRouterGroup:
    """Tests for the RouterGroup prefixing helper."""

    @pytest.fixture
    def router(self):
        """Provide a fresh router."""
        return MenuRouter(storage=MemoryStorage())

    def test_handler_decorator_prefixes(self, router):
        """RouterGroup.handler registers under '<prefix>.<name>'."""
        group = RouterGroup("users", router)

        @group.handler("edit")
        async def edit(update, ctx, params):
            pass

        assert "users.edit" in router.list_handlers()

    def test_register_handler_prefixes(self, router):
        """RouterGroup.register_handler also applies the prefix."""
        group = RouterGroup("admin", router)

        async def ban(update, ctx, params):
            pass

        group.register_handler("ban", ban)
        assert "admin.ban" in router.list_handlers()
