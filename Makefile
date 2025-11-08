# Makefile for Telegram Menu Builder development

.PHONY: help install install-dev clean test test-cov lint format type-check pre-commit build docs

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install package
	pip install -e .

install-dev:  ## Install package with development dependencies
	pip install -e ".[dev]"
	pre-commit install

clean:  ## Clean build artifacts and cache
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type f -name '*.coverage' -delete

test:  ## Run tests
	pytest

test-cov:  ## Run tests with coverage report
	pytest --cov --cov-report=html --cov-report=term

lint:  ## Run linter
	ruff check src tests

format:  ## Format code
	black src tests
	ruff check --fix src tests

type-check:  ## Run type checkers
	mypy src
	pyright

pre-commit:  ## Run pre-commit hooks on all files
	pre-commit run --all-files

build:  ## Build package
	python -m build

publish-test:  ## Publish to TestPyPI
	python -m twine upload --repository testpypi dist/*

publish:  ## Publish to PyPI
	python -m twine upload dist/*

docs:  ## Build documentation
	cd docs && make html
