# Telegram Menu Builder

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Type Checked: pyright](https://img.shields.io/badge/type%20checked-pyright-blue)](https://github.com/microsoft/pyright)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting: ruff](https://img.shields.io/badge/linting-ruff-red)](https://github.com/astral-sh/ruff)

A powerful, type-safe Python library for creating recursive inline keyboard menus in [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v20+.

## ✨ Features

- 🏗️ **Builder Pattern API** - Intuitive, fluent interface for menu construction
- 🔐 **Type-Safe** - Full type hints with Python 3.12+, validated with Pyright
- 📦 **Smart Callback Encoding** - Automatically handles Telegram's 64-byte limit
- 💾 **Hybrid Storage** - Inline, temporary (Redis), and persistent (SQL) strategies
- 🔄 **Unlimited Nesting** - Create complex multi-level menus with breadcrumb support
- ⚡ **Async-First** - Built for modern async/await patterns
- 🧩 **Pluggable Storage** - Bring your own storage backend
- 🎨 **Flexible Layouts** - Grid layouts, custom columns, navigation buttons
- 🧪 **Well Tested** - Comprehensive test suite with 90%+ coverage

## 🚀 Quick Start

### Installation

```bash
pip install telegram-menu-builder
```

### Basic Usage

```python
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from telegram_menu_builder import MenuBuilder, MenuRouter

# Create a menu
async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    menu = (MenuBuilder()
        .add_item("🌍 Language", handler="set_language")
        .add_item("👤 Profile", handler="edit_profile")
        .add_item("🔔 Notifications", handler="notifications")
        .columns(2)
        .add_back_button()
        .build())
    
    await update.message.reply_text("⚙️ Settings", reply_markup=menu)

# Route callbacks
router = MenuRouter()

@router.handler("set_language")
async def handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict) -> None:
    # Handle language selection
    pass

# Register with application
app = Application.builder().token("YOUR_TOKEN").build()
app.add_handler(CallbackQueryHandler(router.route))
```

## 📚 Advanced Examples

### Multi-Level Menus with Parameters

```python
menu = (MenuBuilder()
    .add_item(
        "📝 Edit User",
        handler="edit_user",
        user_id=123,
        field="email",
        breadcrumb=["settings", "users"],
        validation_required=True
    )
    .add_item(
        "🗑️ Delete User",
        handler="delete_user",
        user_id=123,
        confirm=True
    )
    .columns(1)
    .add_back_button(handler="user_list", page=2)
    .build())
```

### Submenu Navigation

```python
# Main menu
main_menu = MenuBuilder()

# Create submenu
user_submenu = (MenuBuilder()
    .add_item("Add User", handler="add_user")
    .add_item("List Users", handler="list_users")
    .add_back_button())

# Add submenu to main menu
main_menu.add_submenu("👥 Users", user_submenu)
```

### Custom Storage Backend

```python
from telegram_menu_builder import StorageBackend, MenuBuilder
from redis.asyncio import Redis

class RedisStorage(StorageBackend):
    def __init__(self, redis_client: Redis) -> None:
        self.redis = redis_client
    
    async def set(self, key: str, data: dict, ttl: int) -> None:
        await self.redis.setex(key, ttl, json.dumps(data))
    
    async def get(self, key: str) -> dict | None:
        value = await self.redis.get(key)
        return json.loads(value) if value else None

# Use custom storage
storage = RedisStorage(redis_client)
builder = MenuBuilder(storage_manager=storage)
```

## 🏗️ Architecture

The library follows a clean architecture with separation of concerns:

```
MenuBuilder (API Layer)
    ↓
MenuAction (Data encoding/decoding)
    ↓
StorageManager (Strategy selection)
    ↓
StorageBackend (Interface)
    ├── MemoryStorage
    ├── RedisStorage
    └── SQLStorage
```

### Callback Data Encoding

The library intelligently encodes callback data based on size:

1. **Inline** (< 60 bytes): Encoded directly in callback_data
2. **Short-term** (60-500 bytes): Stored in Redis/Memory with TTL
3. **Persistent** (> 500 bytes): Stored in database

```python
# Automatic strategy selection
action = MenuAction(
    handler="complex_handler",
    params={
        "user_id": 123,
        "filters": {"active": True, "role": "admin"},
        "breadcrumb": ["main", "users", "edit"],
        "metadata": {...}
    }
)
# Library automatically chooses best storage strategy
```

## 🧪 Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/smoxy/telegram-menu-builder.git
cd telegram-menu-builder

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/test_builder.py

# Run type checking
mypy src
pyright
```

### Code Quality

```bash
# Format code
black src tests

# Lint code
ruff check src tests

# Run all pre-commit hooks
pre-commit run --all-files
```

## 📖 Documentation

Full documentation is available at: [https://telegram-menu-builder.readthedocs.io](https://telegram-menu-builder.readthedocs.io)

- [API Reference](docs/api_reference.md)
- [Advanced Usage](docs/advanced.md)
- [Storage Backends](docs/storage.md)
- [Migration Guide](docs/migration.md)

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🏗️ Architecture Highlights

### Intelligent Callback Data Management
- **Automatic Strategy Selection**: Chooses between inline, short-term, and persistent storage
- **Compression**: Zlib compression for inline data
- **Deduplication**: Same data = same storage key
- **64-byte Limit**: Automatically handles Telegram's callback_data constraint

### Type Safety
- **Pydantic v2**: Runtime validation with static type support
- **Pyright Strict**: 100% type coverage with strict checking
- **MyPy Compatible**: Dual type checker validation
- **Python 3.12+**: Modern type hints (generics, Self, Protocol)

### Storage Architecture
```
CallbackData → Encoder → Strategy Selector
                              ├─ Inline (< 60 bytes)
                              ├─ Short-term Storage (60-500 bytes, TTL)
                              └─ Persistent Storage (> 500 bytes)
```

## 🙏 Acknowledgments

- Built for [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v20+
- Inspired by real-world Telegram bot development challenges
- Type checking powered by [Pyright](https://github.com/microsoft/pyright)
- Validation powered by [Pydantic](https://github.com/pydantic/pydantic) v2

## 📊 Project Status

This project is currently in **alpha** stage. APIs may change before 1.0.0 release.

- ✅ Core builder API
- ✅ Callback encoding/decoding
- ✅ Memory storage backend
- 🚧 Redis storage backend (in progress)
- 🚧 SQL storage backend (in progress)
- 📅 Pagination support (planned)
- 📅 Template system (planned)
- 📅 Form wizard support (planned)

## � Publishing to PyPI

If you want to contribute or publish your own fork:

### Build the Package

```bash
# Install build tools
pip install build twine

# Build distribution files
python -m build

# Verify the build
twine check dist/*
```

### Upload to PyPI

See [PYPI_CONFIG.md](PYPI_CONFIG.md) for detailed instructions on configuring your PyPI token.

```bash
# Using the provided script
python upload_to_pypi.py

# Or manually
twine upload dist/*
```

## �💬 Support

- 📫 Report bugs: [GitHub Issues](https://github.com/smoxy/telegram-menu-builder/issues)
- 💡 Request features: [GitHub Discussions](https://github.com/smoxy/telegram-menu-builder/discussions)
- 📧 Email: info@sf-paris.dev

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### Why MIT License?

The MIT License is chosen to maximize accessibility and enable diverse use cases:

- ✅ **Free to use** - Commercial, private, or personal projects
- ✅ **Free to modify** - Adapt the code to your needs
- ✅ **Free to distribute** - Share with others or on package managers
- ✅ **Training AI Models** - Explicitly permitted - this code can be used for training machine learning models and AI systems
- ✅ **Minimal requirements** - Only requires attribution and license inclusion

**IMPORTANT:** This project can be used for training AI models. If you use this code to train language models, code-generation models, or any other AI systems, you are explicitly permitted to do so under the MIT License.

### Attribution

If you use this project, we appreciate (but don't require) attribution:

```
Telegram Menu Builder - MIT License
Copyright (c) 2025 Simone Flavio Paris
https://github.com/smoxy/telegram-menu-builder
```

---

Made with ❤️ for the Telegram Bot community
