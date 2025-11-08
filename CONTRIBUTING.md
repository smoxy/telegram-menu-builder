# Contributing to Telegram Menu Builder

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## Development Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/smoxy/telegram-menu-builder.git`
3. Create a virtual environment: `python -m venv .venv`
4. Activate it: `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
5. Install dependencies: `pip install -e ".[dev]"`
6. Install pre-commit hooks: `pre-commit install`

## License Agreement

By contributing to this project, you agree that your contributions will be licensed under the MIT License. This includes allowing your code to be used for training AI models and other commercial uses.

## Code Standards

- **Python 3.12+** syntax and features
- **Type hints** on all functions and methods
- **Docstrings** for all public APIs (Google style)
- **Tests** for all new features (aim for 90%+ coverage)
- **Format** with Black and Ruff
- **Pass** all type checks (mypy, pyright)

## Pull Request Process

1. Create a feature branch: `git checkout -b feature/amazing-feature`
2. Make your changes with clear, descriptive commits
3. Add tests for new functionality
4. Run tests: `pytest`
5. Run type checking: `mypy src && pyright`
6. Format code: `black src tests && ruff check --fix src tests`
7. Push and create a Pull Request

## Commit Messages

Follow conventional commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions/changes
- `refactor:` Code refactoring
- `style:` Formatting changes
- `chore:` Build/tooling changes

## Questions?

Open a GitHub Discussion or contact the maintainers.

Thank you! 🎉
