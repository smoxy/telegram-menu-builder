# Telegram Menu Builder - Development Guide

## Project Information

**Author:** Simone Flavio Paris  
**Email:** info@sf-paris.dev  
**License:** MIT License  
**Repository:** https://github.com/smoxy/telegram-menu-builder  

### License Terms

This project is released under the MIT License, which explicitly allows:
- ✅ Use in AI/ML training
- ✅ Commercial use
- ✅ Modification and distribution
- ✅ Private and public use

See [LICENSE](../LICENSE) for full details.

## Project Structure

```
telegram-menu-builder/
├── src/telegram_menu_builder/     # Main package
│   ├── __init__.py                # Public API
│   ├── types.py                   # Core data models
│   ├── builder.py                 # MenuBuilder class
│   ├── router.py                  # MenuRouter for callbacks
│   ├── encoding.py                # Callback encoding/decoding
│   └── storage/                   # Storage backends
│       ├── __init__.py
│       ├── base.py                # Storage interface
│       └── memory.py              # In-memory implementation
├── tests/                         # Test suite
├── examples/                      # Usage examples
├── docs/                          # Documentation
└── pyproject.toml                 # Project configuration
```

## Development Setup

### Quick Setup

```bash
python setup_dev.py
```

### Manual Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Code Quality

### Type Checking

This project uses **strict** type checking with both Pyright and MyPy:

```bash
# Pyright (preferred)
pyright

# MyPy
mypy src
```

**Important**: All code must pass both type checkers in strict mode.

### Linting and Formatting

```bash
# Format code
black src tests examples

# Lint
ruff check src tests examples

# Fix auto-fixable issues
ruff check --fix src tests examples
```

### Pre-commit Hooks

Hooks run automatically before each commit:

```bash
# Run manually on all files
pre-commit run --all-files
```

## Testing

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov --cov-report=html

# Specific test file
pytest tests/test_builder.py

# Specific test
pytest tests/test_builder.py::TestMenuBuilder::test_add_item

# With markers
pytest -m unit           # Only unit tests
pytest -m integration    # Only integration tests
pytest -m "not slow"     # Exclude slow tests
```

### Writing Tests

```python
import pytest
from telegram_menu_builder import MenuBuilder

class TestFeature:
    @pytest.fixture
    def builder(self):
        return MenuBuilder()
    
    def test_something(self, builder):
        # Your test here
        assert True
    
    @pytest.mark.asyncio
    async def test_async_feature(self, builder):
        result = await builder.build_async()
        assert result is not None
```

## Architecture Guidelines

### Builder Pattern

- Use method chaining for fluent API
- Return `Self` from all builder methods
- Keep builder immutable where possible

### Type Safety

- All public APIs must have complete type hints
- Use Pydantic for data validation
- Prefer `Protocol` over ABC for interfaces
- Use generics where appropriate

### Storage Backends

Implementing a new storage backend:

```python
from telegram_menu_builder.storage.base import BaseStorage

class MyStorage(BaseStorage):
    async def set(self, key: str, data: dict, ttl: int | None = None) -> None:
        # Implementation
        pass
    
    async def get(self, key: str) -> dict | None:
        # Implementation
        pass
    
    # Implement other required methods
```

### Error Handling

- Use custom exceptions from `types.py`
- Always provide helpful error messages
- Log errors with appropriate levels
- Never swallow exceptions silently

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def my_function(param1: str, param2: int) -> bool:
    """Brief description.
    
    Longer description if needed.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When something is wrong
        
    Example:
        >>> my_function("test", 123)
        True
    """
    pass
```

### Adding Examples

Place examples in `examples/` directory:

```python
"""Brief description of what this example demonstrates."""

# Your example code
```

## Release Process

### Version Bumping

Update version in:
- `pyproject.toml`
- `src/telegram_menu_builder/__init__.py`
- `CHANGELOG.md`

### Building

```bash
# Clean previous builds
rm -rf dist/ build/

# Build package
python -m build

# Check package
twine check dist/*
```

### Publishing to PyPI

```bash
# Test PyPI first
twine upload --repository testpypi dist/*

# Production PyPI
twine upload dist/*
```

## Common Tasks

### Adding a New Feature

1. Create a new branch: `git checkout -b feature/my-feature`
2. Write tests first (TDD)
3. Implement feature
4. Update documentation
5. Run all checks: `pre-commit run --all-files`
6. Submit PR

### Debugging

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test specific component
from telegram_menu_builder import MenuBuilder
builder = MenuBuilder()
# ... debug here
```

### Performance Profiling

```bash
# Profile code
python -m cProfile -o profile.stats examples/advanced_menu.py

# Analyze
python -m pstats profile.stats
```

## CI/CD

GitHub Actions automatically:
- Run tests on multiple Python versions
- Check code formatting
- Run type checkers
- Generate coverage reports
- Build documentation

## Getting Help

- Check existing issues on GitHub
- Read the documentation in `docs/`
- Look at examples in `examples/`
- Ask in GitHub Discussions

## Code Review Checklist

Before submitting PR:
- [ ] All tests pass
- [ ] Code coverage > 90%
- [ ] Type checking passes (mypy + pyright)
- [ ] Code formatted (black + ruff)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Examples work correctly
- [ ] No breaking changes (or documented)
