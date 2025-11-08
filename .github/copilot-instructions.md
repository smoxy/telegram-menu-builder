# Telegram Menu Builder - Copilot Instructions

## Project Overview
This is a professional Python library for creating recursive inline keyboard menus for python-telegram-bot v20+.
Uses Builder Pattern with intelligent callback data encoding and hybrid storage strategies.

## Key Technologies
- Python 3.12+ with full type hints
- python-telegram-bot v20+
- Pydantic v2 for data validation
- Pyright for static type checking
- pytest + pytest-asyncio for testing

## Code Style Guidelines
- Use async/await for all telegram handlers
- Full type annotations with Python 3.12 features (generics, TypedDict)
- Prefer dataclasses over regular classes for data structures
- Use Protocol classes for interfaces
- Follow Builder pattern principles
- Keep storage strategies abstracted

## Architecture Principles
- No business logic coupling - library must be generic
- Storage backend must be pluggable
- Callback data encoding must handle 64-byte Telegram limit
- Support unlimited nested menu levels
- Type-safe API with IDE autocomplete support

## Project Structure
```
src/telegram_menu_builder/    # Main package
tests/                         # Test suite
examples/                      # Usage examples
docs/                          # Documentation
```

## Development Workflow
1. Write types first (types.py)
2. Implement core logic with tests
3. Add examples for each feature
4. Update documentation

## Testing Requirements
- 90%+ code coverage
- Test async handlers
- Mock telegram API calls
- Test all storage strategies
