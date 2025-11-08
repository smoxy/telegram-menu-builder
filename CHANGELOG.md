# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2025-11-08

### Added
- Comprehensive guide for using MenuBuilder with ConversationHandler
- New example `conversation_handler_menu.py` demonstrating proper `per_message` configuration
- Documentation file `docs/conversation_handler_guide.md` with best practices
- Support for python-telegram-bot up to version 22.5

### Changed
- Updated dependency range: `python-telegram-bot>=20.0,<22.6` (was `<22.0`)
- Clarified ConversationHandler integration requirements in documentation

### Fixed
- Documented solution for `CallbackQueryHandler` in fallbacks not working with `per_message=False`
- Added warning about PTBUserWarning when using incompatible handler types with `per_message=True`

## [0.1.0] - 2025-11-08

### Added
- Initial alpha release
- Core functionality for menu building
- MenuBuilder with fluent API
- CallbackEncoder with intelligent storage strategies
- MenuRouter for callback handling
- MemoryStorage backend
- Type-safe interfaces with Pydantic v2
- Full Pyright/MyPy type checking
- Comprehensive test suite
- Example applications
- Documentation

[Unreleased]: https://github.com/smoxy/telegram-menu-builder/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/smoxy/telegram-menu-builder/releases/tag/v0.1.1
[0.1.0]: https://github.com/smoxy/telegram-menu-builder/releases/tag/v0.1.0

