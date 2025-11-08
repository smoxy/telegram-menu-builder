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

### The Solution

Set `per_message=True`:

```python
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("list", show_list)],
    states={},
    fallbacks=[
        CallbackQueryHandler(router.route)
    ],
    per_message=True  # ✅ REQUIRED for callbacks after END
)
```

**Now it works:**
1. ✅ User sends `/list`
2. ✅ `show_list` executes and returns `END`
3. ✅ Message with "Next" button is sent
4. ✅ User clicks "Next" → Callback is processed
5. ✅ `CallbackQueryHandler` in fallbacks receives the callback

---

## Common Patterns

### Pattern 1: Pagination (Stateless)

**Use Case**: Display paginated data where each page is independent.

**Configuration**:
```python
ConversationHandler(
    entry_points=[CommandHandler("list", show_first_page)],
    states={},
    fallbacks=[CallbackQueryHandler(router.route)],
    per_message=True  # ✅ Required
)
```

**Why**: Entry point returns `END`, but pagination buttons need to work.

**Example**: See `examples/conversation_handler_menu.py`

---

### Pattern 2: Settings Menu (Stateless)

**Use Case**: Display a settings menu where each option is independent.

**Configuration**:
```python
ConversationHandler(
    entry_points=[CommandHandler("settings", show_settings)],
    states={},
    fallbacks=[CallbackQueryHandler(router.route)],
    per_message=True  # ✅ Required
)
```

**Why**: Settings command returns `END`, but toggle buttons need to work.

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

**Use Case**: Some states are stateful, some buttons work outside states.

**Configuration**:
```python
EDITING = range(1)

ConversationHandler(
    entry_points=[CommandHandler("edit", show_edit_menu)],
    states={
        EDITING: [
            MessageHandler(filters.TEXT, handle_edit_input),
            CallbackQueryHandler(router.route, pattern="^edit_")
        ]
    },
    fallbacks=[
        CallbackQueryHandler(router.route, pattern="^menu_"),  # Outside states
        CommandHandler("cancel", cancel)
    ],
    per_message=True  # ✅ Required for fallback callbacks
)
```

**Why**: Fallback callbacks need to work after some handlers return `END`.

---

## Best Practices

### ✅ DO

1. **Set `per_message=True`** when:
   - Entry points return `ConversationHandler.END`
   - You send inline keyboards from entry points
   - You want fallback `CallbackQueryHandler` to process callbacks

2. **Document the setting** in code comments:
   ```python
   ConversationHandler(
       # ...
       per_message=True,  # Required: entry points return END but send keyboards
   )
   ```

3. **Test both paths**:
   - Send command and immediately click button
   - Send command, end conversation, then click button

4. **Use clear callback patterns**:
   ```python
   fallbacks=[
       CallbackQueryHandler(router.route, pattern="^menu_"),  # Only menu callbacks
       CommandHandler("cancel", cancel)  # Other fallbacks
   ]
   ```

### ❌ DON'T

1. **Don't assume default works**:
   ```python
   # ❌ BAD - Callback won't work after END
   ConversationHandler(
       entry_points=[CommandHandler("list", returns_end)],
       fallbacks=[CallbackQueryHandler(router.route)]
       # Missing: per_message=True
   )
   ```

2. **Don't mix incompatible handlers** with `per_message=True`:
   ```python
   # ⚠️ WARNING - Will raise PTBUserWarning
   ConversationHandler(
       entry_points=[
           CommandHandler("start", cmd_handler),  # Not a CallbackQueryHandler
       ],
       per_message=True  # Requires all handlers to be CallbackQueryHandler
   )
   ```
   
   **Solution**: If you need `per_message=True`, use `CallbackQueryHandler` for entry points:
   ```python
   # ✅ GOOD
   ConversationHandler(
       entry_points=[
           CallbackQueryHandler(start_from_button, pattern="^start$")
       ],
       per_message=True
   )
   ```
   
   Or keep `per_message=False` and use active states instead of fallbacks:
   ```python
   # ✅ ALTERNATIVE
   ConversationHandler(
       entry_points=[CommandHandler("start", cmd_handler)],
       states={
           ACTIVE: [CallbackQueryHandler(router.route)]
       },
       per_message=False  # OK - handlers work within states
   )
   ```

3. **Don't ignore warnings**:
   ```
   PTBUserWarning: If 'per_message=False', 'CallbackQueryHandler' will not be 
   tracked for every message.
   ```
   This warning means your callbacks might not work as expected.

---

## Troubleshooting

### Issue 1: Callbacks Not Working

**Symptoms**:
- ✅ Command executes
- ✅ Inline keyboard appears
- ❌ Clicking button does nothing
- ❌ No handler logs

**Solution**: Set `per_message=True`

**Debug checklist**:
```python
# 1. Check if entry point returns END
async def my_command(...) -> int:
    # ...
    return ConversationHandler.END  # ← This is the issue

# 2. Check if you send inline keyboard
menu = MenuBuilder().add_item(...).build()
await update.message.reply_text(..., reply_markup=menu)  # ← And this

# 3. Check per_message setting
ConversationHandler(
    # ...
    per_message=False  # ← This must be True!
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
- User navigates menu, state resets
- Context data lost between clicks

**Cause**: Using `per_message=True` when state needed

**Solution**: Keep conversation active (don't return `END`):
```python
BROWSING = range(1)

async def show_menu(...) -> int:
    # ...
    return BROWSING  # Keep state active

ConversationHandler(
    entry_points=[CommandHandler("menu", show_menu)],
    states={
        BROWSING: [CallbackQueryHandler(router.route)]
    },
    per_message=False  # OK - conversation stays active
)
```

---

## Summary Table

| Pattern | Entry Returns | Keyboards? | Fallback Callbacks? | per_message |
|---------|--------------|------------|---------------------|-------------|
| Pagination | `END` | ✅ Yes | ✅ Yes | `True` ✅ |
| Settings Menu | `END` | ✅ Yes | ✅ Yes | `True` ✅ |
| Multi-Step Form | State | ❌ No | ❌ No | `False` ✅ |
| Inline Menu | State | ✅ Yes | ❌ No (in states) | `False` ✅ |
| Mixed | `END` or State | ✅ Yes | ✅ Yes | `True` ✅ |

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
