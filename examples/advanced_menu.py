"""Advanced example with nested menus and complex parameters.

This example demonstrates:
- Multi-level menu navigation
- Breadcrumb tracking
- Complex parameter passing
- Pagination
"""

import logging
from typing import Any
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from telegram_menu_builder import MenuBuilder, MenuRouter


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Router
router = MenuRouter()


# Mock database
USERS = [
    {"id": i, "name": f"User {i}", "email": f"user{i}@example.com", "active": i % 2 == 0}
    for i in range(1, 26)  # 25 users
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show main admin menu."""
    menu = (
        MenuBuilder()
        .add_item("👥 Manage Users", handler="user_management")
        .add_item("📊 Statistics", handler="show_stats")
        .add_item("⚙️ Settings", handler="show_settings")
        .columns(2)
        .build()
    )

    await update.message.reply_text("🎛️ Admin Panel\n\nSelect an option:", reply_markup=menu)


@router.handler("user_management")
async def handle_user_management(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict[str, Any]
) -> None:
    """Show user management submenu."""
    menu = (
        MenuBuilder()
        .add_item("📋 List Users", handler="list_users", page=1)
        .add_item("➕ Add User", handler="add_user")
        .add_item("🔍 Search User", handler="search_user")
        .columns(1)
        .add_back_button(handler="go_home")
        .build()
    )

    await update.callback_query.edit_message_text(
        "👥 User Management\n\nChoose an action:", reply_markup=menu
    )


@router.handler("list_users")
async def handle_list_users(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict[str, Any]
) -> None:
    """List users with pagination."""
    page = params.get("page", 1)
    per_page = 5

    # Calculate pagination
    total_users = len(USERS)
    total_pages = (total_users + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total_users)

    users_on_page = USERS[start_idx:end_idx]

    # Build menu
    builder = MenuBuilder()

    # Add user buttons
    for user in users_on_page:
        status = "✅" if user["active"] else "❌"
        builder.add_item(
            f"{status} {user['name']}",
            handler="view_user",
            user_id=user["id"],
            page=page,  # Remember current page for back navigation
            breadcrumb=["user_management", "list_users"],
        )

    builder.columns(1)

    # Add pagination buttons
    if page > 1:
        builder.add_back_button(text="⬅️ Previous", handler="list_users", page=page - 1)

    if page < total_pages:
        builder.add_next_button(text="➡️ Next", handler="list_users", page=page + 1)

    # Add back to menu button
    builder.add_item("🔙 Back to Menu", handler="user_management")

    menu = builder.build()

    await update.callback_query.edit_message_text(
        f"📋 Users (Page {page}/{total_pages})\n\n"
        f"Showing users {start_idx + 1}-{end_idx} of {total_users}",
        reply_markup=menu,
    )


@router.handler("view_user")
async def handle_view_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict[str, Any]
) -> None:
    """View user details."""
    user_id = params["user_id"]
    page = params.get("page", 1)
    breadcrumb = params.get("breadcrumb", [])

    # Find user
    user = next((u for u in USERS if u["id"] == user_id), None)

    if not user:
        await update.callback_query.answer("User not found", show_alert=True)
        return

    # Build menu with edit options
    menu = (
        MenuBuilder()
        .add_item(
            "✏️ Edit Name",
            handler="edit_user_field",
            user_id=user_id,
            field="name",
            page=page,
            breadcrumb=breadcrumb + ["view_user"],
        )
        .add_item(
            "📧 Edit Email",
            handler="edit_user_field",
            user_id=user_id,
            field="email",
            page=page,
            breadcrumb=breadcrumb + ["view_user"],
        )
        .add_item(
            "🔄 Toggle Active",
            handler="toggle_user_active",
            user_id=user_id,
            page=page,
            breadcrumb=breadcrumb,
        )
        .add_item(
            "🗑️ Delete User",
            handler="confirm_delete_user",
            user_id=user_id,
            page=page,
            breadcrumb=breadcrumb,
        )
        .columns(2)
        .add_back_button(text="🔙 Back to List", handler="list_users", page=page)
        .build()
    )

    status = "Active ✅" if user["active"] else "Inactive ❌"

    await update.callback_query.edit_message_text(
        f"👤 User Details\n\n"
        f"ID: {user['id']}\n"
        f"Name: {user['name']}\n"
        f"Email: {user['email']}\n"
        f"Status: {status}",
        reply_markup=menu,
    )


@router.handler("edit_user_field")
async def handle_edit_user_field(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict[str, Any]
) -> None:
    """Edit a user field."""
    field = params["field"]

    await update.callback_query.answer(
        f"To edit {field}, send the new value in chat", show_alert=True
    )


@router.handler("toggle_user_active")
async def handle_toggle_user_active(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict[str, Any]
) -> None:
    """Toggle user active status."""
    user_id = params["user_id"]

    # Find and toggle user
    user = next((u for u in USERS if u["id"] == user_id), None)
    if user:
        user["active"] = not user["active"]
        status = "activated" if user["active"] else "deactivated"
        await update.callback_query.answer(f"User {status}")

    # Refresh view
    await handle_view_user(update, context, params)


@router.handler("confirm_delete_user")
async def handle_confirm_delete_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict[str, Any]
) -> None:
    """Show delete confirmation."""
    user_id = params["user_id"]
    page = params.get("page", 1)

    menu = (
        MenuBuilder()
        .add_item("⚠️ YES, DELETE", handler="delete_user", user_id=user_id, page=page)
        .add_item("❌ Cancel", handler="view_user", user_id=user_id, page=page)
        .columns(1)
        .build()
    )

    await update.callback_query.edit_message_text(
        f"⚠️ Confirm Deletion\n\n"
        f"Are you sure you want to delete user #{user_id}?\n\n"
        f"This action cannot be undone!",
        reply_markup=menu,
    )


@router.handler("delete_user")
async def handle_delete_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict[str, Any]
) -> None:
    """Delete a user."""
    user_id = params["user_id"]
    page = params.get("page", 1)

    # Delete user
    global USERS
    USERS = [u for u in USERS if u["id"] != user_id]

    await update.callback_query.answer("User deleted successfully")

    # Return to list
    await handle_list_users(update, context, {"page": page})


@router.handler("go_home")
async def handle_go_home(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict[str, Any]
) -> None:
    """Go back to main menu."""
    menu = (
        MenuBuilder()
        .add_item("👥 Manage Users", handler="user_management")
        .add_item("📊 Statistics", handler="show_stats")
        .add_item("⚙️ Settings", handler="show_settings")
        .columns(2)
        .build()
    )

    await update.callback_query.edit_message_text(
        "🎛️ Admin Panel\n\nSelect an option:", reply_markup=menu
    )


@router.handler("show_stats")
@router.handler("show_settings")
@router.handler("add_user")
@router.handler("search_user")
async def handle_not_implemented(
    update: Update, context: ContextTypes.DEFAULT_TYPE, params: dict[str, Any]
) -> None:
    """Placeholder for not implemented features."""
    await update.callback_query.answer("This feature is not implemented yet", show_alert=True)


def main() -> None:
    """Start the bot."""
    application = Application.builder().token("YOUR_BOT_TOKEN_HERE").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(router.route))

    logger.info("Advanced example bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
