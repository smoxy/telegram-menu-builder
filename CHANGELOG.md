# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-03

### Fixed
- **Critical:** callback data is no longer lost when a menu is built inside a running
  event loop. `add_item()` previously discarded the handler and parameters in async
  contexts, producing buttons with empty `callback_data`; encoding is now deferred to
  `build_async()` so every item is encoded correctly.
- `MenuBuilder.build()` now works when called inside a running event loop (it runs the
  async build on a short-lived worker thread) instead of raising `RuntimeError`. In async
  code, prefer `await build_async()`.
- `add_submenu()` no longer stores the non-serializable submenu builder in callback params
  (which broke encoding the moment it ran); only a JSON-safe `_submenu_id` is stored, with
  the builder kept in an internal registry accessible via the new `get_submenu()`.
- Corrected `__version__`, which was hard-coded to `0.1.0` while the package was `0.1.1`;
  it is now single-sourced from the installed package metadata.
- Hardened the deterministic dedup hash in `CallbackEncoder` with
  `hashlib.md5(..., usedforsecurity=False)` (resolves Bandit B324).

### Added
- Exported the exception hierarchy (`MenuBuilderError`, `EncodingError`, `DecodingError`,
  `StorageError`, `ValidationError`) from the package root.
- `MenuBuilder.get_submenu()` to retrieve a registered submenu builder by id.
- MkDocs Material documentation site (`mkdocs.yml`, `docs/`), including a dependency/CVE
  audit page and a Python-compatibility analysis.
- Tests for the router, storage backends, type validators, and package metadata (overall
  coverage raised from ~62% to ~90%).
- Continuous-integration workflow (ruff, black, mypy, pyright, pytest, pip-audit) on every
  push and pull request, plus a documentation-deploy workflow.
- Project metadata: `SECURITY.md`, Dependabot configuration, and issue/PR templates.
- Claude Code maintenance tooling (`CLAUDE.md`, `AGENTS.md`, `.claude/` agents and skills).

### Changed
- Raised the pydantic floor to `>=2.4` to exclude CVE-2024-3772 (ReDoS in pydantic email
  validation, fixed in 2.4.0). The library does not use email validation, so it was never
  exploitable here; the bump is defense-in-depth.
- `StorageStrategy` now subclasses `enum.StrEnum`.
- Refactored the navigation-button methods and `MenuRouter.route()` for clarity with no
  behavior change; removed the `# noqa: PLR0912` suppression.
- Added a `[docs]` optional-dependency group, `pip-audit` to `[dev]`, and a `[tool.bandit]`
  configuration.

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

[Unreleased]: https://github.com/smoxy/telegram-menu-builder/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/smoxy/telegram-menu-builder/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/smoxy/telegram-menu-builder/releases/tag/v0.1.1
[0.1.0]: https://github.com/smoxy/telegram-menu-builder/releases/tag/v0.1.0

