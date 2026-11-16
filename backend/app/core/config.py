"""Centralized application settings and configuration management."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables with defaults."""

    model_config = SettingsConfigDict(
        env_file=(_ENV_FILE, ".env"),
        env_file_encoding="utf-8-sig",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Mode
    ENVIRONMENT: str = Field(
        default="development",
        description="Deployment environment: development, staging, or production",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Application logging level (DEBUG, INFO, WARNING, ERROR)",
    )

    # Database Settings
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/campusfix",
        description="Async SQLAlchemy database connection string (PostgreSQL with asyncpg)",
    )
    TEST_DATABASE_URL: str | None = Field(
        default=None,
        description="Optional dedicated test database connection string",
    )
    DB_POOL_SIZE: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of permanent connections to keep in the connection pool",
    )
    DB_MAX_OVERFLOW: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum number of connections that can be created beyond DB_POOL_SIZE",
    )
    DB_POOL_TIMEOUT: float = Field(
        default=30.0,
        ge=1.0,
        description="Seconds to wait before giving up on getting a connection from the pool",
    )
    DB_POOL_RECYCLE: int = Field(
        default=1800,
        ge=60,
        description="Recycle connections older than this threshold (seconds) to prevent stale sockets",
    )
    DB_POOL_PRE_PING: bool = Field(
        default=True,
        description="Test connections for liveness upon checkout (pessimistic disconnect handling)",
    )
    DB_ECHO: bool = Field(
        default=False,
        description="Log all SQL statements to stdout (strictly for local debugging)",
    )

    # Security & Tokens
    SECRET_KEY: str = Field(
        default="placeholder_secret_key_minimum_64_hex_chars_for_development_only0000",
        min_length=32,
        description="Cryptographic secret key for signing JWT tokens",
    )
    ALGORITHM: str = Field(
        default="HS256",
        description="JWT cryptographic signing algorithm",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=15,
        ge=1,
        description="Lifetime of short-lived access tokens in minutes",
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        ge=1,
        description="Lifetime of refresh token cookie in days",
    )
    COOKIE_SECURE: bool | None = Field(
        default=None,
        description=(
            "Whether to enforce the Secure flag on refresh cookies. "
            "If None, auto-detected from ENVIRONMENT (True in production and staging, False in development)."
        ),
    )

    # CORS
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-separated allowed origins for CORS headers",
    )

    @field_validator("DATABASE_URL", "TEST_DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str | None) -> str | None:
        """Normalizes database URLs, safely encoding special characters in credentials using URL.create()."""
        if v is None:
            return None
        if not isinstance(v, str) or not v.strip():
            return v
        stripped = v.strip()
        if "://" in stripped:
            scheme, rest = stripped.split("://", 1)
            # Detect unencoded '@' characters in credentials
            if rest.count("@") > 1 and "/" in rest:
                userpass, host_db = rest.rsplit("@", 1)
                if ":" in userpass:
                    user, pwd = userpass.split(":", 1)
                    host_port, db = host_db.split("/", 1) if "/" in host_db else (host_db, "")
                    port = None
                    if ":" in host_port:
                        host, port_str = host_port.split(":", 1)
                        port = int(port_str) if port_str.isdigit() else None
                    else:
                        host = host_port
                    return URL.create(
                        drivername=scheme,
                        username=user,
                        password=pwd,
                        host=host,
                        port=port,
                        database=db if db else None,
                    ).render_as_string(hide_password=False)
        return stripped

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_async_db_url(cls, v: str) -> str:
        """Enforces that the database connection URL utilizes an async driver."""
        if not v or not v.strip():
            raise ValueError("DATABASE_URL cannot be empty")
        stripped = v.strip()
        if not (
            stripped.startswith("postgresql+asyncpg://")
            or stripped.startswith("sqlite+aiosqlite://")
        ):
            driver_prefix = stripped.split("://")[0] if "://" in stripped else stripped
            raise ValueError(
                f"DATABASE_URL must specify an async driver ('postgresql+asyncpg://'). "
                f"Received driver: '{driver_prefix}://'"
            )
        return stripped

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Enforces that production environments cannot execute with placeholder or weak secrets."""
        if self.is_production:
            insecure_placeholders = {
                "placeholder_secret_key_minimum_64_hex_chars_for_development_only0000",
                "secret",
                "changeme",
                "your-secret-key-here",
            }
            if (
                self.SECRET_KEY in insecure_placeholders
                or "placeholder" in self.SECRET_KEY.lower()
                or len(self.SECRET_KEY) < 64
            ):
                raise ValueError(
                    "Production environment requires a strong, random SECRET_KEY with minimum "
                    "64 hex characters (256 bits). Insecure placeholders or weak keys are strictly forbidden."
                )
        return self

    @property
    def cors_origins(self) -> list[str]:
        """Parsed list of allowed CORS origins."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def masked_database_url(self) -> str:
        """Returns the database connection URL with credentials safely masked for diagnostics."""
        try:
            url = make_url(self.DATABASE_URL)
            return url.render_as_string(hide_password=True)
        except Exception:
            return "<invalid-database-url>"

    @property
    def is_production(self) -> bool:
        """Returns True if the application is executing in production mode."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_cookie_secure(self) -> bool:
        """Determines whether refresh cookies require the Secure attribute (HTTPS).

        If COOKIE_SECURE is explicitly configured (True or False), that value takes precedence.
        Otherwise, Secure=True is enforced in production and staging environments,
        while defaulting to False in development/testing to allow local HTTP operation.
        """
        if self.COOKIE_SECURE is not None:
            return self.COOKIE_SECURE
        return self.ENVIRONMENT.lower() in ("production", "staging")


@lru_cache
def get_settings() -> Settings:
    """Returns a cached instance of application Settings."""
    return Settings()


settings = get_settings()
