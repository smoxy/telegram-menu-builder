"""Pytest configuration and fixtures."""

import pytest


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


@pytest.fixture
def sample_user_data():
    """Provide sample user data for testing."""
    return {
        "user_id": 123,
        "name": "Test User",
        "email": "test@example.com",
        "active": True,
    }


@pytest.fixture
def sample_menu_params():
    """Provide sample menu parameters for testing."""
    return {
        "page": 1,
        "filters": {"active": True},
        "breadcrumb": ["main", "users"],
    }
