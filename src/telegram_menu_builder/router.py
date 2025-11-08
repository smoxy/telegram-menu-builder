"""Menu router for handling callback queries.

This module provides a routing system that dispatches callback queries to
registered handler functions based on the decoded callback data.
"""

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from telegram_menu_builder.encoding import CallbackEncoder
from telegram_menu_builder.storage import MemoryStorage, StorageBackend
from telegram_menu_builder.types import DecodingError

logger = logging.getLogger(__name__)


# Type alias for handler functions
HandlerFunc = Callable[[Update, ContextTypes.DEFAULT_TYPE, dict[str, Any]], Awaitable[None]]


class MenuRouter:
    """Router for dispatching callback queries to handlers.

    This class manages handler registration and routes incoming callback queries
    to the appropriate handler function based on the decoded action.

    Attributes:
        storage: Storage backend for callback data
        encoder: Callback data encoder/decoder
        handlers: Mapping of handler names to functions
        default_handler: Fallback handler for unknown actions

    Example:
        >>> router = MenuRouter()
        >>>
        >>> @router.handler("edit_user")
        >>> async def handle_edit(update, context, params):
        ...     user_id = params["user_id"]
        ...     # Handle edit...
        >>>
        >>> # Register with application
        >>> app.add_handler(CallbackQueryHandler(router.route))
    """

    def __init__(
        self,
        storage: StorageBackend | None = None,
        default_handler: HandlerFunc | None = None,
        auto_answer: bool = True,
    ) -> None:
        """Initialize menu router.

        Args:
            storage: Storage backend (defaults to MemoryStorage)
            default_handler: Optional fallback handler for unknown actions
            auto_answer: Automatically answer callback queries
        """
        self._storage = storage or MemoryStorage()
        self._encoder = CallbackEncoder(self._storage)
        self._handlers: dict[str, HandlerFunc] = {}
        self._default_handler = default_handler
        self._auto_answer = auto_answer

        # Middleware hooks
        self._before_handlers: list[HandlerFunc] = []
        self._after_handlers: list[HandlerFunc] = []
        self._error_handlers: list[
            Callable[[Update, ContextTypes.DEFAULT_TYPE, Exception], Awaitable[None]]
        ] = []

    def handler(self, name: str) -> Callable[[HandlerFunc], HandlerFunc]:
        """Decorator to register a handler function.

        Args:
            name: Handler name (must match handler in MenuAction)

        Returns:
            Decorator function

        Example:
            >>> @router.handler("edit_user")
            >>> async def handle_edit(update, context, params):
            ...     user_id = params["user_id"]
            ...     await update.callback_query.edit_message_text(f"Editing user {user_id}")
        """

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self.register_handler(name, func)
            return func

        return decorator

    def register_handler(self, name: str, func: HandlerFunc) -> None:
        """Register a handler function.

        Args:
            name: Handler name
            func: Async handler function

        Example:
            >>> async def my_handler(update, context, params):
            ...     pass
            >>> router.register_handler("my_action", my_handler)
        """
        if name in self._handlers:
            logger.warning(f"Overwriting existing handler for '{name}'")

        self._handlers[name] = func

    def register_handlers(self, handlers: Mapping[str, HandlerFunc]) -> None:
        """Register multiple handlers at once.

        Args:
            handlers: Mapping of handler names to functions

        Example:
            >>> router.register_handlers({
            ...     "action1": handle_action1,
            ...     "action2": handle_action2,
            ... })
        """
        for name, func in handlers.items():
            self.register_handler(name, func)

    def unregister_handler(self, name: str) -> bool:
        """Unregister a handler.

        Args:
            name: Handler name to remove

        Returns:
            True if handler was removed, False if not found
        """
        if name in self._handlers:
            del self._handlers[name]
            return True
        return False

    def set_default_handler(self, func: HandlerFunc) -> None:
        """Set the default fallback handler.

        Args:
            func: Async handler function
        """
        self._default_handler = func

    async def route(  # noqa: PLR0912
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Route a callback query to the appropriate handler.

        This is the main entry point that should be registered with
        CallbackQueryHandler in python-telegram-bot.

        Args:
            update: Telegram Update object
            context: Telegram Context object

        Example:
            >>> app.add_handler(CallbackQueryHandler(router.route))
        """
        if not update.callback_query:
            logger.warning("route() called with Update without callback_query")
            return

        callback_query = update.callback_query
        callback_data = callback_query.data

        if not callback_data:
            logger.warning("Callback query has no data")
            if self._auto_answer:
                await callback_query.answer()
            return

        try:
            # Decode callback data
            action = await self._encoder.decode(callback_data)
            params = action.params
            handler_name = action.handler

            logger.debug(f"Routing to handler '{handler_name}' with params: {params}")

            # Run before middleware
            for before_handler in self._before_handlers:
                await before_handler(update, context, params)

            # Find and execute handler
            handler = self._handlers.get(handler_name)

            if handler:
                await handler(update, context, params)
            elif self._default_handler:
                logger.debug(f"Handler '{handler_name}' not found, using default handler")
                await self._default_handler(update, context, params)
            else:
                logger.warning(f"No handler registered for '{handler_name}' and no default handler")
                if self._auto_answer:
                    await callback_query.answer("Action not available")
                return

            # Run after middleware
            for after_handler in self._after_handlers:
                await after_handler(update, context, params)

            # Auto-answer callback query
            if self._auto_answer:
                await callback_query.answer()

        except DecodingError as e:
            logger.error(f"Failed to decode callback data: {e}")

            # Run error handlers
            for error_handler in self._error_handlers:
                await error_handler(update, context, e)

            if self._auto_answer:
                await callback_query.answer("Invalid or expired action")

        except Exception as e:
            logger.exception(f"Error handling callback query: {e}")

            # Run error handlers
            for error_handler in self._error_handlers:
                await error_handler(update, context, e)

            if self._auto_answer:
                await callback_query.answer("An error occurred")

    def before(self, func: HandlerFunc) -> HandlerFunc:
        """Register a before middleware handler.

        These run before the main handler for every callback.

        Args:
            func: Async middleware function

        Returns:
            The function (for use as decorator)

        Example:
            >>> @router.before
            >>> async def log_callback(update, context, params):
            ...     logger.info(f"Callback received: {params}")
        """
        self._before_handlers.append(func)
        return func

    def after(self, func: HandlerFunc) -> HandlerFunc:
        """Register an after middleware handler.

        These run after the main handler for every callback.

        Args:
            func: Async middleware function

        Returns:
            The function (for use as decorator)

        Example:
            >>> @router.after
            >>> async def cleanup(update, context, params):
            ...     # Cleanup logic
            ...     pass
        """
        self._after_handlers.append(func)
        return func

    def on_error(
        self, func: Callable[[Update, ContextTypes.DEFAULT_TYPE, Exception], Awaitable[None]]
    ) -> Callable[[Update, ContextTypes.DEFAULT_TYPE, Exception], Awaitable[None]]:
        """Register an error handler.

        These run when an exception occurs during routing or handling.

        Args:
            func: Async error handler function

        Returns:
            The function (for use as decorator)

        Example:
            >>> @router.on_error
            >>> async def handle_error(update, context, error):
            ...     logger.error(f"Error: {error}")
            ...     await update.callback_query.answer("Something went wrong")
        """
        self._error_handlers.append(func)
        return func

    def get_handler(self, name: str) -> HandlerFunc | None:
        """Get a registered handler by name.

        Args:
            name: Handler name

        Returns:
            Handler function or None if not found
        """
        return self._handlers.get(name)

    def list_handlers(self) -> list[str]:
        """Get list of all registered handler names.

        Returns:
            List of handler names
        """
        return list(self._handlers.keys())

    @property
    def storage(self) -> StorageBackend:
        """Get the storage backend."""
        return self._storage

    @property
    def encoder(self) -> CallbackEncoder:
        """Get the callback encoder."""
        return self._encoder


class RouterGroup:
    """Group multiple routers with a common prefix.

    This is useful for organizing handlers by feature or module.

    Example:
        >>> users = RouterGroup("users", main_router)
        >>> @users.handler("edit")
        >>> async def edit_user(update, context, params):
        ...     # Handler will be registered as "users.edit"
        ...     pass
    """

    def __init__(self, prefix: str, router: MenuRouter) -> None:
        """Initialize router group.

        Args:
            prefix: Prefix for all handlers in this group
            router: Parent MenuRouter instance
        """
        self.prefix = prefix
        self.router = router

    def handler(self, name: str) -> Callable[[HandlerFunc], HandlerFunc]:
        """Decorator to register a handler with prefix.

        Args:
            name: Handler name (will be prefixed)

        Returns:
            Decorator function
        """
        full_name = f"{self.prefix}.{name}"
        return self.router.handler(full_name)

    def register_handler(self, name: str, func: HandlerFunc) -> None:
        """Register a handler with prefix.

        Args:
            name: Handler name (will be prefixed)
            func: Async handler function
        """
        full_name = f"{self.prefix}.{name}"
        self.router.register_handler(full_name, func)
