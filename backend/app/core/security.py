"""Authentication and cryptographic security primitives for CampusFix.

Provides reusable Argon2id password hashing and PyJWT access token encoding/decoding.
Adheres strictly to RFC 9106 Argon2id parameters, HS256 JWT signature verification,
and defensible error handling without logging or leaking credentials.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from app.core.config import settings
from app.models.user import UserRole

# Standard Argon2id configuration aligned with RFC 9106 recommendations
_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

TOKEN_TYPE_ACCESS = "access"
RESERVED_CLAIMS = frozenset({"sub", "email", "role", "exp", "iat", "type"})


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id.

    Args:
        password: The plaintext password string to hash.

    Returns:
        The resulting Argon2id hash string with embedded parameters and unique salt.

    Raises:
        ValueError: If the password is empty or not a string.
    """
    if not password or not isinstance(password, str):
        raise ValueError("Password cannot be empty")
    return _password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Safely verifies a plaintext password against an Argon2id hash.

    Never logs or stores the plaintext password. Safely handles malformed, corrupted,
    or mismatched hashes by returning False without leaking internal exceptions.

    Args:
        plain_password: The candidate plaintext password to test.
        hashed_password: The stored Argon2id hash string to compare against.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    if not plain_password or not hashed_password:
        return False
    if not isinstance(plain_password, str) or not isinstance(hashed_password, str):
        return False

    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except Argon2Error:
        return False
    except (TypeError, ValueError):
        return False


def create_access_token(
    user_id: str | uuid.UUID,
    email: str,
    role: str | UserRole,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
    secret_key: str | None = None,
    algorithm: str | None = None,
) -> str:
    """Creates a signed, short-lived JWT access token for an authenticated user.

    Args:
        user_id: UUID or string identifier of the user (bound as 'sub' claim).
        email: Institutional email address of the user.
        role: Domain role of the user (e.g. STUDENT, STAFF, ADMINISTRATOR).
        expires_delta: Optional custom lifetime timedelta. Defaults to settings.ACCESS_TOKEN_EXPIRE_MINUTES.
        extra_claims: Optional supplementary claims (cannot override reserved claims).
        secret_key: Optional cryptographic signing key. Defaults to settings.SECRET_KEY.
        algorithm: Optional signing algorithm. Defaults to settings.ALGORITHM (HS256).

    Returns:
        Encoded and cryptographically signed JWT string.

    Raises:
        ValueError: If user_id, email, or role are empty or invalid.
    """
    if not user_id:
        raise ValueError("user_id cannot be empty")
    if not email or not isinstance(email, str) or not email.strip():
        raise ValueError("email cannot be empty")
    if not role:
        raise ValueError("role cannot be empty")

    key = secret_key or settings.SECRET_KEY
    alg = algorithm or settings.ALGORITHM

    now = datetime.now(UTC)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    role_str = role.value if hasattr(role, "value") else str(role)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email.strip(),
        "role": role_str,
        "type": TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    if extra_claims:
        for claim_key, claim_val in extra_claims.items():
            if claim_key not in RESERVED_CLAIMS:
                payload[claim_key] = claim_val

    return jwt.encode(payload, key, algorithm=alg)


def decode_access_token(
    token: str,
    secret_key: str | None = None,
    algorithms: list[str] | None = None,
) -> dict[str, Any]:
    """Decodes, verifies signature, algorithm, and validates claims of an access JWT.

    Args:
        token: Raw JWT access token string to validate.
        secret_key: Optional secret key to verify against. Defaults to settings.SECRET_KEY.
        algorithms: Optional list of permitted algorithms. Defaults to [settings.ALGORITHM].

    Returns:
        Decoded token payload dictionary.

    Raises:
        jwt.DecodeError: If the token is not a valid non-empty string or malformed.
        jwt.ExpiredSignatureError: If the token has expired past 'exp'.
        jwt.InvalidSignatureError: If the token cryptographic signature is invalid.
        jwt.InvalidAlgorithmError: If the token algorithm is not permitted.
        jwt.MissingRequiredClaimError: If a mandatory claim is missing.
        jwt.InvalidTokenError: If the token is not an access token or fails verification.
    """
    if not token or not isinstance(token, str):
        raise jwt.DecodeError("Token must be a non-empty string")

    key = secret_key or settings.SECRET_KEY
    allowed_algorithms = algorithms or [settings.ALGORITHM]

    payload = jwt.decode(
        token,
        key,
        algorithms=allowed_algorithms,
        options={
            "require": ["exp", "iat", "sub"],
            "verify_exp": True,
            "verify_iat": True,
            "verify_signature": True,
        },
    )

    # Validate mandatory domain claims
    for required_claim in ("email", "role", "type"):
        if (
            required_claim not in payload
            or payload[required_claim] is None
            or payload[required_claim] == ""
        ):
            raise jwt.MissingRequiredClaimError(f"Token is missing the '{required_claim}' claim")

    # Strictly enforce token type
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise jwt.InvalidTokenError(
            f"Invalid token type: expected '{TOKEN_TYPE_ACCESS}', received '{payload.get('type')}'"
        )

    return payload
