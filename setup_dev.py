"""Setup script for development environment."""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, description: str) -> bool:
    """Run a shell command and print status.
    
    Args:
        cmd: Command to run
        description: Description of what the command does
        
    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        print(e.stderr)
        return False


def main():
    """Setup development environment."""
    print("\n🚀 Setting up Telegram Menu Builder development environment\n")
    
    # Check Python version
    if sys.version_info < (3, 12):
        print("❌ Python 3.12+ is required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Install package in editable mode with dev dependencies
    if not run_command(
        "pip install -e \".[dev]\"",
        "Installing package with dev dependencies"
    ):
        print("\n❌ Failed to install dependencies")
        sys.exit(1)
    
    # Install pre-commit hooks
    if not run_command(
        "pre-commit install",
        "Installing pre-commit hooks"
    ):
        print("\n⚠️  Warning: Failed to install pre-commit hooks")
    
    # Run initial code formatting
    print("\n" + "="*60)
    print("  Running initial code formatting")
    print("="*60)
    
    run_command("black src tests", "Formatting with Black")
    run_command("ruff check --fix src tests", "Linting with Ruff")
    
    # Run type checking
    print("\n" + "="*60)
    print("  Running type checkers")
    print("="*60)
    
    run_command("mypy src", "Type checking with MyPy")
    run_command("pyright", "Type checking with Pyright")
    
    # Run tests
    print("\n" + "="*60)
    print("  Running tests")
    print("="*60)
    
    run_command("pytest", "Running test suite")
    
    print("\n" + "="*60)
    print("  ✅ Setup Complete!")
    print("="*60)
    print("\nDevelopment environment is ready!")
    print("\nUseful commands:")
    print("  pytest              - Run tests")
    print("  pytest --cov        - Run tests with coverage")
    print("  black src tests     - Format code")
    print("  ruff check src      - Lint code")
    print("  mypy src            - Type check with MyPy")
    print("  pyright             - Type check with Pyright")
    print("  pre-commit run -a   - Run all pre-commit hooks")
    print("\nSee README.md for more information.")


if __name__ == "__main__":
    main()
