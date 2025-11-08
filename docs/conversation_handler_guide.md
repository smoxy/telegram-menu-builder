# Using MenuBuilder with ConversationHandler

This guide explains how to properly integrate `telegram-menu-builder` with `python-telegram-bot`'s `ConversationHandler`.

## Table of Contents

- [Overview](#overview)
- [The per_message Setting](#the-per_message-setting)
- [Common Patterns](#common-patterns)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

`MenuBuilder` and `MenuRouter` can be used both **inside** and **outside** a `ConversationHandler`. However, when using them inside a `ConversationHandler`, you need to understand the implications of the `per_message` setting.

---

## The per_message Setting

### What is per_message?

The `per_message` parameter in `ConversationHandler` determines whether the conversation state is tracked:
- **Per user** (`per_message=False`, default)
- **Per message** (`per_message=True`)

### Why it Matters for MenuBuilder

When using `CallbackQueryHandler` (which `MenuRouter.route` is) in `ConversationHandler.fallbacks`, the `per_message` setting affects whether your menu callbacks are processed after the conversation ends.

### The Problem

Consider this common pattern:

```python
async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Command that shows a paginated list."""
    # Build menu with navigation buttons
    menu = (
        MenuBuilder()
        .add_item("Next ➡️", handler="paginate", page=1)
        .build()
    )
    
    await update.message.reply_text("Page 1", reply_markup=menu)
    
    # Return END - no conversation state needed
    return ConversationHandler.END

# Register handlers
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("list", show_list)],
    states={},
    fallbacks=[
        CallbackQueryHandler(router.route)  # Handle pagination
    ],
    per_message=False  # ⚠️ DEFAULT - CALLBACKS WON'T WORK!
)
```

**What happens:**
1. ✅ User sends `/list`
2. ✅ `show_list` executes and returns `END`
3. ✅ Message with "Next" button is sent
4. ❌ User clicks "Next" → **Nothing happens**
5. ❌ `CallbackQueryHandler` in fallbacks **never receives the callback**

### The Solution (Recommended)

**Keep conversation active** by returning a state instead of `END`:

```python
BROWSING = 0

async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Command that shows a paginated list."""
    menu = (
        MenuBuilder()
        .add_item("Next ➡️", handler="paginate", page=1)
        .build()
    )
    
    await update.message.reply_text("Page 1", reply_markup=menu)
    
    # Return state to keep conversation active
    return BROWSING

# ✅ CORRECT: Use states, not fallbacks
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("list", show_list)],
    states={
        BROWSING: [
            CallbackQueryHandler(router.route)  # Handles pagination
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel)
    ],
    per_message=False  # ✅ Default works fine!
)
```

**Now it works:**
1. ✅ User sends `/list`
2. ✅ `show_list` executes and returns `BROWSING` state
3. ✅ Message with "Next" button is sent
4. ✅ User clicks "Next" → Callback is processed
5. ✅ `CallbackQueryHandler` in `BROWSING` state receives the callback

### Alternative Solution: per_message=True

If you **must** return `END` and use fallbacks, you need `per_message=True`:

```python
# ⚠️ WARNING: This triggers PTBUserWarning with CommandHandler
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("list", show_list)],  # ❌ Not a CallbackQueryHandler
    states={},
    fallbacks=[CallbackQueryHandler(router.route)],
    per_message=True  # ⚠️ Causes warning with CommandHandler
)
```

**Problem:** You'll get:
```
PTBUserWarning: If 'per_message=True', all entry points, state handlers, 
and fallbacks must be 'CallbackQueryHandler'
```

**Solution if you need per_message=True:**
```python
# ✅ Use only CallbackQueryHandler (no CommandHandler)
conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_from_button, pattern="^start$")  # ✅ All callbacks
    ],
    states={},
    fallbacks=[
        CallbackQueryHandler(router.route)
    ],
    per_message=True  # ✅ No warning
)
```

**Recommendation:** Use the first solution (states with `per_message=False`) - it's simpler and more flexible.

---

## Common Patterns

### Pattern 1: Pagination (Stateful - Recommended)

**Use Case**: Display paginated data where navigation should work seamlessly.

**Configuration**:
```python
BROWSING = 0

ConversationHandler(
    entry_points=[CommandHandler("list", show_first_page)],  # Returns BROWSING
    states={
        BROWSING: [CallbackQueryHandler(router.route)]
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False  # ✅ Default works fine
)
```

**Why**: Conversation stays active, callbacks work in state handlers.

**Example**: See `examples/conversation_handler_menu.py`

---

### Pattern 2: Settings Menu (Stateful)

**Use Case**: Display a settings menu where navigation should persist.

**Configuration**:
```python
SETTINGS = 0

ConversationHandler(
    entry_points=[CommandHandler("settings", show_settings)],  # Returns SETTINGS
    states={
        SETTINGS: [CallbackQueryHandler(router.route)]
    },
    fallbacks=[CommandHandler("done", done)],
    per_message=False  # ✅ Default works fine
)
```

**Why**: Settings navigation works within the SETTINGS state.

---

### Pattern 3: Multi-Step Form (Stateful)

**Use Case**: Collect user input across multiple steps.

**Configuration**:
```python
WAITING_NAME, WAITING_AGE = range(2)

ConversationHandler(
    entry_points=[CommandHandler("register", start_registration)],
    states={
        WAITING_NAME: [MessageHandler(filters.TEXT, handle_name)],
        WAITING_AGE: [MessageHandler(filters.TEXT, handle_age)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False  # ✅ Can use default
)
```

**Why**: Conversation stays active (doesn't return `END`), so callbacks in states work fine.

---

### Pattern 4: Hybrid (Mixed)

**Use Case**: Some states are stateful, navigation works throughout.

**Configuration**:
```python
BROWSING, EDITING = range(2)

ConversationHandler(
    entry_points=[CommandHandler("edit", show_edit_menu)],  # Returns BROWSING
    states={
        BROWSING: [
            CallbackQueryHandler(router.route, pattern="^menu_")
        ],
        EDITING: [
            MessageHandler(filters.TEXT, handle_edit_input),
            CallbackQueryHandler(router.route, pattern="^edit_")
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel)
    ],
    per_message=False  # ✅ Default works fine
)
```

**Why**: All callbacks are handled in states, not fallbacks.

---

### Pattern 5: Button-Only Menu (per_message=True)

**Use Case**: Entire bot is button-driven, no text commands in conversation.

**Configuration**:
```python
ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_menu, pattern="^start$")  # ✅ Only callbacks
    ],
    states={
        MENU: [
            CallbackQueryHandler(router.route)  # ✅ Only callbacks
        ]
    },
    fallbacks=[
        CallbackQueryHandler(go_back, pattern="^back$")  # ✅ Only callbacks
    ],
    per_message=True  # ✅ Safe - all handlers are CallbackQueryHandler
)
```

**Why**: When ALL handlers are `CallbackQueryHandler`, `per_message=True` works without warnings.

---

## Best Practices

### ✅ DO

1. **Use states instead of fallbacks** for menu callbacks:
   ```python
   # ✅ GOOD - Callbacks in states
   ConversationHandler(
       entry_points=[CommandHandler("list", show_list)],  # Returns state
       states={
           BROWSING: [CallbackQueryHandler(router.route)]
       }
   )
   ```

2. **Keep conversation active** when users are navigating:
   ```python
   async def show_list(...) -> int:
       # Show menu
       return BROWSING  # ✅ Keep state active
   ```

3. **Document your conversation flow** in code comments:
   ```python
   ConversationHandler(
       # Entry -> BROWSING (user navigates pages)
       # BROWSING -> END (user clicks "Done")
   )
   ```

4. **Use `per_message=False`** (default) with `CommandHandler` entry points:
   ```python
   ConversationHandler(
       entry_points=[CommandHandler("start", start)],
       # per_message=False,  # Default - works with CommandHandler
   )
   ```

### ❌ DON'T

1. **Don't return END if you need callbacks to work**:
   ```python
   # ❌ BAD - Callbacks won't work in fallbacks with per_message=False
   async def show_list(...) -> int:
       # Show menu with buttons
       return ConversationHandler.END  # ❌ Buttons won't work
   
   ConversationHandler(
       entry_points=[CommandHandler("list", show_list)],
       fallbacks=[CallbackQueryHandler(router.route)]  # ❌ Won't receive callbacks
   )
   ```

2. **Don't mix CommandHandler with per_message=True**:
   ```python
   # ❌ BAD - Triggers PTBUserWarning
   ConversationHandler(
       entry_points=[
           CommandHandler("start", cmd_handler),  # ❌ Not a CallbackQueryHandler
       ],
       per_message=True  # ❌ Requires all handlers to be CallbackQueryHandler
   )
   ```
   
   **Solution**: Use states with default `per_message=False`:
   ```python
   # ✅ GOOD
   ConversationHandler(
       entry_points=[CommandHandler("start", cmd_handler)],
       states={
           ACTIVE: [CallbackQueryHandler(router.route)]
       },
       per_message=False  # ✅ OK - default
   )
   ```

3. **Don't use fallbacks for menu navigation**:
   ```python
   # ❌ BAD - Fallbacks are for escaping, not navigation
   ConversationHandler(
       states={...},
       fallbacks=[
           CallbackQueryHandler(router.route)  # ❌ Use states instead
       ]
   )
   ```
   
   **Solution**: Put callbacks in states:
   ```python
   # ✅ GOOD
   ConversationHandler(
       states={
           MENU: [CallbackQueryHandler(router.route)]  # ✅ In state
       },
       fallbacks=[
           CommandHandler("cancel", cancel)  # ✅ Escape command
       ]
   )
   ```

---

## Troubleshooting

### Issue 1: Callbacks Not Working

**Symptoms**:
- ✅ Command executes
- ✅ Inline keyboard appears
- ❌ Clicking button does nothing
- ❌ No handler logs

**Solution**: Use states, not fallbacks:

```python
BROWSING = 0

# ✅ CORRECT
async def my_command(...) -> int:
    # Show menu
    return BROWSING  # Keep conversation active

ConversationHandler(
    entry_points=[CommandHandler("list", my_command)],
    states={
        BROWSING: [CallbackQueryHandler(router.route)]  # ✅ Callbacks work here
    },
    per_message=False  # Default
)
```

### Issue 2: PTBUserWarning with per_message=True

**Symptoms**:
```
PTBUserWarning: If 'per_message=True', all entry points, state handlers, 
and fallbacks must be 'CallbackQueryHandler'
```

**Cause**: Mixing `CommandHandler` with `per_message=True`

**Solution A** - Use only `CallbackQueryHandler`:
```python
ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_from_button, pattern="^start$")
    ],
    per_message=True
)
```

**Solution B** - Use states instead of fallbacks:
```python
ACTIVE = range(1)

async def cmd_handler(...) -> int:
    # ...
    return ACTIVE  # Keep conversation active

ConversationHandler(
    entry_points=[CommandHandler("start", cmd_handler)],
    states={
        ACTIVE: [CallbackQueryHandler(router.route)]
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False  # OK - no conflict
)
```

### Issue 3: Multiple Handlers Triggered

**Symptoms**:
- Multiple handlers process same callback
- Duplicate responses

**Cause**: Pattern overlap between handlers

**Solution**: Use specific patterns:
```python
fallbacks=[
    CallbackQueryHandler(router.route, pattern="^menu_"),  # Only "menu_*"
    CallbackQueryHandler(other_handler, pattern="^other_")  # Only "other_*"
]
```

### Issue 4: State Not Persisting

**Symptoms**:
- User navigates menu, unexpected behavior
- Context data accessible throughout navigation

**Cause**: This is actually **correct** behavior with states!

**Explanation**: When using states (recommended pattern), conversation stays active:
```python
BROWSING = 0

async def show_menu(...) -> int:
    # ...
    return BROWSING  # State persists

ConversationHandler(
    entry_points=[CommandHandler("menu", show_menu)],
    states={
        BROWSING: [CallbackQueryHandler(router.route)]
    },
    per_message=False  # Conversation stays active until END
)
```

This allows `context.user_data` to persist across navigation, which is usually desired.

---

## Summary Table

| Pattern | Entry Returns | Keyboards? | Handler Location | per_message | Warning? |
|---------|--------------|------------|------------------|-------------|----------|
| Stateful Navigation (✅ Recommended) | State | ✅ Yes | States | `False` ✅ | No |
| Multi-Step Form | State | ❌ No | States | `False` ✅ | No |
| Button-Only Bot | State | ✅ Yes | States + Entry (all callbacks) | `True` ✅ | No |
| ❌ END + Fallbacks + Command | `END` | ✅ Yes | Fallbacks | `False` ❌ | ⚠️ Callbacks don't work |
| ❌ END + Fallbacks + Command | `END` | ✅ Yes | Fallbacks | `True` ❌ | ⚠️ PTBUserWarning |

---

## Additional Resources

- [python-telegram-bot FAQ: per_* settings](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do)
- [ConversationHandler Documentation](https://docs.python-telegram-bot.org/en/stable/telegram.ext.conversationhandler.html)
- [Example: conversation_handler_menu.py](../examples/conversation_handler_menu.py)

---

## Questions?

If you encounter issues not covered here:

1. Check your `per_message` setting matches your pattern
2. Review the example in `examples/conversation_handler_menu.py`
3. Enable DEBUG logging to see what's happening
4. Open an issue on GitHub with a minimal reproduction

---

**Last Updated**: November 2025  
**Library Version**: 0.1.1+  
**PTB Version**: 20.0 - 22.5
