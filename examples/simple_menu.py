"""Simple example demonstrating basic menu creation and handling.

This example shows how to create a simple settings menu with language selection.
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from telegram_menu_builder import MenuBuilder, MenuRouter


# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# Create router
router = MenuRouter()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message with settings menu."""
    # Create a simple menu
    menu = (
        MenuBuilder()
        .add_item("🌍 Language", handler="select_language")
        .add_item("👤 Profile", handler="show_profile")
        .add_item("🔔 Notifications", handler="toggle_notifications")
        .columns(2)
        .add_exit_button(text="❌ Close", handler="close_menu")
        .build()
    )

    await update.message.reply_text("⚙️ Settings\n\nChoose an option:", reply_markup=menu)


@router.handler("select_language")
async def handle_language_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict
) -> None:
    """Show language selection submenu."""
    menu = (
        MenuBuilder()
        .add_item("🇮🇹 Italiano", handler="set_language", lang="it")
        .add_item("🇬🇧 English", handler="set_language", lang="en")
        .add_item("🇪🇸 Español", handler="set_language", lang="es")
        .add_item("🇩🇪 Deutsch", handler="set_language", lang="de")
        .columns(2)
        .add_back_button(handler="show_main_menu")
        .build()
    )

    await update.callback_query.edit_message_text("🌍 Select your language:", reply_markup=menu)


@router.handler("set_language")
async def handle_set_language(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict
) -> None:
    """Set user language."""
    lang = params["lang"]

    # Save language (you would save to database here)
    context.user_data["language"] = lang

    lang_names = {"it": "Italiano", "en": "English", "es": "Español", "de": "Deutsch"}

    await update.callback_query.answer(f"Language set to {lang_names.get(lang, lang)}")

    # Return to main menu
    await show_main_menu(update, context, params)


@router.handler("show_main_menu")
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict) -> None:
    """Show main settings menu."""
    menu = (
        MenuBuilder()
        .add_item("🌍 Language", handler="select_language")
        .add_item("👤 Profile", handler="show_profile")
        .add_item("🔔 Notifications", handler="toggle_notifications")
        .columns(2)
        .add_exit_button(text="❌ Close", handler="close_menu")
        .build()
    )

    await update.callback_query.edit_message_text(
        "⚙️ Settings\n\nChoose an option:", reply_markup=menu
    )


@router.handler("show_profile")
async def handle_show_profile(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict
) -> None:
    """Show user profile."""
    user = update.effective_user

    menu = (
        MenuBuilder()
        .add_item("✏️ Edit Name", handler="edit_profile", field="name")
        .add_item("📧 Edit Email", handler="edit_profile", field="email")
        .columns(1)
        .add_back_button(handler="show_main_menu")
        .build()
    )

    await update.callback_query.edit_message_text(
        f"👤 Profile\n\n" f"Name: {user.first_name}\n" f"Username: @{user.username or 'N/A'}",
        reply_markup=menu,
    )


@router.handler("edit_profile")
async def handle_edit_profile(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict
) -> None:
    """Handle profile editing."""
    field = params["field"]

    await update.callback_query.answer(
        f"To edit {field}, send me the new value in chat", show_alert=True
    )


@router.handler("toggle_notifications")
async def handle_toggle_notifications(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict
) -> None:
    """Toggle notifications on/off."""
    # Get current state
    enabled = context.user_data.get("notifications", True)

    # Toggle
    context.user_data["notifications"] = not enabled

    status = "enabled" if not enabled else "disabled"
    await update.callback_query.answer(f"Notifications {status}")

    # Return to main menu
    await show_main_menu(update, context, params)


@router.handler("close_menu")
async def handle_close_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict
) -> None:
    """Close the menu."""
    await update.callback_query.delete_message()


def main() -> None:
    """Start the bot."""
    # Create application
    application = Application.builder().token("YOUR_BOT_TOKEN_HERE").build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(router.route))

    # Start bot
    logger.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
