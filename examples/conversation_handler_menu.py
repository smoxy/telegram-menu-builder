"""Example using MenuBuilder with ConversationHandler.

This example demonstrates how to use MenuBuilder within a ConversationHandler,
including proper configuration of per_message settings for callback handling.

IMPORTANT: When using CallbackQueryHandler in ConversationHandler fallbacks,
you MUST set per_message=True if your entry points return ConversationHandler.END
and you want the fallback handlers to process callbacks from inline keyboards.

See: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do
"""

import logging
from typing import Any

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from telegram_menu_builder import MenuBuilder, MenuRouter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Router for menu callbacks
router = MenuRouter()


# Mock data for pagination
ITEMS = [f"Item {i}" for i in range(1, 101)]  # 100 items


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point command that shows paginated list.
    
    Returns ConversationHandler.END because we don't need conversation state
    for simple pagination - the fallback CallbackQueryHandler will handle
    navigation between pages.
    """
    logger.info("start command called")
    
    # Show first page
    await _show_page(update, context, page=0)
    
    # Return END - no conversation state needed
    # Fallback handlers will process pagination callbacks
    return ConversationHandler.END


async def _show_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int
) -> None:
    """Display a page of items with navigation buttons."""
    items_per_page = 10
    start = page * items_per_page
    end = start + items_per_page
    page_items = ITEMS[start:end]
    
    total_pages = (len(ITEMS) + items_per_page - 1) // items_per_page
    
    # Build message
    message = f"📋 Page {page + 1}/{total_pages}\n\n"
    message += "\n".join(f"• {item}" for item in page_items)
    
    # Build navigation menu
    builder = MenuBuilder()
    
    # Add navigation buttons in a row
    nav_buttons = []
    if page > 0:
        builder.add_item(
            "⬅️ Previous",
            handler="paginate",
            page=page - 1
        )
    
    if end < len(ITEMS):
        builder.add_item(
            "Next ➡️",
            handler="paginate",
            page=page + 1
        )
    
    # Set columns based on number of buttons
    if page > 0 and end < len(ITEMS):
        builder.columns(2)  # Both prev and next
    else:
        builder.columns(1)  # Only one button
    
    menu = builder.build()
    
    # Send or edit message
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message,
            reply_markup=menu
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=menu
        )


@router.handler("paginate")
async def handle_pagination(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    params: dict[str, Any]
) -> None:
    """Handle pagination callbacks from the menu."""
    logger.info(f"handle_pagination called with params: {params}")
    
    page = params["page"]
    await _show_page(update, context, page)


def create_conversation_handler() -> ConversationHandler:
    """Create the ConversationHandler with proper per_message configuration.
    
    CRITICAL: per_message=True is REQUIRED when:
    1. Entry points return ConversationHandler.END
    2. You send messages with inline keyboards
    3. You want fallback CallbackQueryHandler to process those callbacks
    
    Without per_message=True, the fallback CallbackQueryHandler will NOT
    receive callback queries after the conversation ends.
    
    See PTB FAQ for more details:
    https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler("list", start)
        ],
        states={
            # No intermediate states needed for simple pagination
        },
        fallbacks=[
            # This handles all menu navigation callbacks
            CallbackQueryHandler(router.route)
        ],
        name="pagination_menu",
        persistent=False,
        # ✅ REQUIRED: per_message=True for CallbackQueryHandler in fallbacks
        # when entry points return END
        per_message=True,
        # Alternative patterns if you don't want per_message=True:
        # 1. Don't return END from entry points (keep conversation active)
        # 2. Use CallbackQueryHandler outside ConversationHandler
        # 3. Use intermediate states instead of fallbacks
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel and end the conversation."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END


def main() -> None:
    """Run the bot."""
    # Replace TOKEN with your bot token
    TOKEN = "YOUR_BOT_TOKEN_HERE"
    
    application = Application.builder().token(TOKEN).build()
    
    # Add ConversationHandler with proper configuration
    application.add_handler(create_conversation_handler())
    
    # Add cancel command
    application.add_handler(CommandHandler("cancel", cancel))
    
    logger.info("Bot started. Try /list to see paginated menu.")
    application.run_polling()


if __name__ == "__main__":
    main()
