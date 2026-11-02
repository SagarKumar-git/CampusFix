"""Pytest configuration and global fixtures for backend test suites."""

import pytest


@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Ensure lru_cache on get_settings does not pollute across tests."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
