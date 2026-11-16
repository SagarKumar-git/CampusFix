"""Unit tests for centralized configuration and settings parsing."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_settings_instantiation():
    """Verifies that default settings load with approved parameters."""
    cfg = Settings()
    assert cfg.ENVIRONMENT == "development"
    assert "postgresql+asyncpg://" in cfg.DATABASE_URL
    assert cfg.DB_POOL_SIZE == 10
    assert cfg.DB_MAX_OVERFLOW == 20
    assert cfg.DB_POOL_TIMEOUT == 30.0
    assert cfg.DB_POOL_RECYCLE == 1800
    assert cfg.DB_POOL_PRE_PING is True
    assert cfg.ALGORITHM == "HS256"
    assert cfg.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert cfg.REFRESH_TOKEN_EXPIRE_DAYS == 7
    assert not cfg.is_production


def test_cors_origins_parsing():
    """Verifies parsing of comma-separated allowed origins."""
    cfg = Settings(
        ALLOWED_ORIGINS="http://localhost:5173, https://campusfix.vercel.app , http://127.0.0.1:5173"
    )
    origins = cfg.cors_origins
    assert len(origins) == 3
    assert "http://localhost:5173" in origins
    assert "https://campusfix.vercel.app" in origins
    assert "http://127.0.0.1:5173" in origins


def test_masked_database_url_masks_password():
    """Verifies that masked_database_url suppresses database credentials for safe logging."""
    cfg = Settings(
        DATABASE_URL="postgresql+asyncpg://admin_user:super_secret_password@db.campus.edu:5432/campusfix"
    )
    masked = cfg.masked_database_url
    assert "super_secret_password" not in masked
    assert "admin_user:***@db.campus.edu:5432/campusfix" in masked


def test_database_url_rejects_empty():
    """Verifies that an empty DATABASE_URL raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(DATABASE_URL="")
    assert "DATABASE_URL cannot be empty" in str(exc_info.value)


def test_database_url_rejects_sync_driver():
    """Verifies that non-async database drivers are rejected to protect async architecture."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(DATABASE_URL="postgresql://postgres:postgres@localhost:5432/campusfix")
    assert "must specify an async driver" in str(exc_info.value)


def test_is_production_flag():
    """Verifies production detection property."""
    dev_cfg = Settings(ENVIRONMENT="development")
    assert not dev_cfg.is_production

    prod_cfg = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )
    assert prod_cfg.is_production


def test_production_rejects_placeholder_secret():
    """Verifies that production environment rejects default placeholder secret."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, ENVIRONMENT="production")
    assert "Production environment requires a strong, random SECRET_KEY" in str(exc_info.value)


def test_production_rejects_short_secret():
    """Verifies that production environment rejects secret shorter than 64 hex characters."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="short_production_secret_key_12345678901234567890",
        )
    assert "Production environment requires a strong, random SECRET_KEY" in str(exc_info.value)


def test_is_cookie_secure_auto_detection():
    """Verifies that cookie Secure flag is auto-detected as True in production & staging, False in dev."""
    dev_cfg = Settings(ENVIRONMENT="development")
    assert dev_cfg.is_cookie_secure is False

    staging_cfg = Settings(ENVIRONMENT="staging")
    assert staging_cfg.is_cookie_secure is True

    prod_cfg = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )
    assert prod_cfg.is_cookie_secure is True


def test_is_cookie_secure_explicit_override():
    """Verifies explicit COOKIE_SECURE setting overrides environment auto-detection."""
    # Force Secure=True in development
    forced_dev_cfg = Settings(ENVIRONMENT="development", COOKIE_SECURE=True)
    assert forced_dev_cfg.is_cookie_secure is True

    # Force Secure=False in staging
    forced_staging_cfg = Settings(ENVIRONMENT="staging", COOKIE_SECURE=False)
    assert forced_staging_cfg.is_cookie_secure is False

    # Force Secure=False in production (e.g. for non-TLS test harness)
    forced_prod_cfg = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        COOKIE_SECURE=False,
    )
    assert forced_prod_cfg.is_cookie_secure is False
