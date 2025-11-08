# Telegram Menu Builder - Quick Start Guide

## Installation

```bash
pip install telegram-menu-builder
```

## Basic Usage

### 1. Create a Simple Menu

```python
from telegram_menu_builder import MenuBuilder

menu = (MenuBuilder()
    .add_item("Option 1", handler="handle_option1")
    .add_item("Option 2", handler="handle_option2")
    .add_item("Option 3", handler="handle_option3")
    .columns(2)
    .build())
```

### 2. Setup Router

```python
from telegram_menu_builder import MenuRouter

router = MenuRouter()

@router.handler("handle_option1")
async def handle_option1(update, context, params):
    await update.callback_query.edit_message_text("You selected Option 1")

@router.handler("handle_option2")
async def handle_option2(update, context, params):
    await update.callback_query.edit_message_text("You selected Option 2")
```

### 3. Register with python-telegram-bot

```python
from telegram.ext import Application, CallbackQueryHandler

app = Application.builder().token("YOUR_TOKEN").build()
app.add_handler(CallbackQueryHandler(router.route))
```

## Advanced Features

### Parameters

Pass unlimited parameters to handlers:

```python
menu = (MenuBuilder()
    .add_item(
        "Edit User",
        handler="edit_user",
        user_id=123,
        field="email",
        breadcrumb=["main", "users"],
        metadata={"source": "admin_panel"}
    )
    .build())
```

### Navigation Buttons

```python
menu = (MenuBuilder()
    .add_item("Item 1", handler="h1")
    .add_item("Item 2", handler="h2")
    .add_back_button(handler="go_back", page=1)
    .add_next_button(handler="go_next", page=3)
    .build())
```

### Nested Menus

```python
# Create submenu
submenu = (MenuBuilder()
    .add_item("Sub Option 1", handler="sub1")
    .add_item("Sub Option 2", handler="sub2")
    .add_back_button())

# Add to main menu
main_menu = (MenuBuilder()
    .add_item("Main Option", handler="main")
    .add_submenu("Open Submenu", submenu)
    .build())
```

### Custom Storage

```python
from telegram_menu_builder import MenuBuilder
from redis.asyncio import Redis

# Use Redis for storage
redis_client = Redis(host='localhost', port=6379)
storage = RedisStorage(redis_client)

builder = MenuBuilder(storage=storage)
```

## Examples

See the `examples/` directory for complete working examples:
- `simple_menu.py` - Basic menu with settings
- `advanced_menu.py` - Multi-level menu with pagination

## Configuration

### Layout

```python
builder = (MenuBuilder()
    .columns(3)        # 3 buttons per row
    .max_rows(5))      # Maximum 5 rows
```

### Storage Strategies

The library automatically chooses the best storage strategy:
- **Inline**: < 60 bytes → encoded in callback_data
- **Short-term**: 60-500 bytes → temporary storage with TTL
- **Persistent**: > 500 bytes → permanent storage

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov

# Type checking
mypy src
pyright
```

## Next Steps

- Read the [API Reference](api_reference.md)
- Check [Advanced Usage](advanced.md)
- Learn about [Storage Backends](storage.md)
