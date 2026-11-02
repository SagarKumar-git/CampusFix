"""Unit tests for Argon2id password hashing and PyJWT access token utilities."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    TOKEN_TYPE_ACCESS,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.user import UserRole

# ==============================================================================
# Password Hashing & Verification Tests (Argon2id)
# ==============================================================================


def test_hash_password_returns_valid_argon2id_format():
    """Verifies that hash_password produces an RFC 9106 Argon2id hash with expected prefix."""
    raw_password = "CorrectHorseBatteryStaple123!"
    hashed = hash_password(raw_password)

    assert hashed.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert raw_password not in hashed
    assert verify_password(raw_password, hashed) is True


def test_hash_password_rejects_empty_or_non_string():
    """Verifies that empty strings or invalid types raise ValueError."""
    with pytest.raises(ValueError, match="Password cannot be empty"):
        hash_password("")

    with pytest.raises(ValueError, match="Password cannot be empty"):
        hash_password(None)  # type: ignore[arg-type]


def test_hash_password_salt_uniqueness():
    """Verifies that hashing the same password twice yields distinct hashes due to salts."""
    raw_password = "DeterministicPassword456!"
    hash_1 = hash_password(raw_password)
    hash_2 = hash_password(raw_password)

    assert hash_1 != hash_2
    assert verify_password(raw_password, hash_1) is True
    assert verify_password(raw_password, hash_2) is True


def test_verify_password_success():
    """Verifies successful verification of matching plaintext password."""
    password = "SecureStaffPassword2026!"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_mismatch():
    """Verifies that an incorrect password returns False without raising exceptions."""
    password = "CorrectPassword123!"
    wrong_password = "WrongPassword123!"
    hashed = hash_password(password)

    assert verify_password(wrong_password, hashed) is False


def test_verify_password_malformed_hashes():
    """Verifies that malformed or garbage hash strings return False safely."""
    assert verify_password("AnyPassword123!", "plain_text_not_a_hash") is False
    assert verify_password("AnyPassword123!", "$argon2id$invalid$hash$data") is False
    assert verify_password("AnyPassword123!", "") is False
    assert verify_password("AnyPassword123!", None) is False  # type: ignore[arg-type]


def test_verify_password_empty_candidate():
    """Verifies that empty candidate passwords return False safely."""
    hashed = hash_password("ValidPassword123!")
    assert verify_password("", hashed) is False
    assert verify_password(None, hashed) is False  # type: ignore[arg-type]


# ==============================================================================
# JWT Creation & Decoding Tests (PyJWT)
# ==============================================================================


def test_create_and_decode_access_token_success():
    """Verifies creation and round-trip decoding of a standard access token."""
    user_id = uuid.uuid4()
    email = "student.demo@campusfix.local"
    role = UserRole.STUDENT

    token = create_access_token(user_id=user_id, email=email, role=role)
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["email"] == email
    assert payload["role"] == "STUDENT"
    assert payload["type"] == TOKEN_TYPE_ACCESS
    assert payload["exp"] > payload["iat"]

    # Verify expiration is roughly 15 minutes in the future
    expected_exp = payload["iat"] + (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    assert abs(payload["exp"] - expected_exp) <= 2


def test_create_access_token_with_custom_lifetime():
    """Verifies that custom expires_delta is respected."""
    user_id = str(uuid.uuid4())
    custom_delta = timedelta(minutes=30)

    token = create_access_token(
        user_id=user_id,
        email="staff.demo@campusfix.local",
        role=UserRole.STAFF,
        expires_delta=custom_delta,
    )
    payload = decode_access_token(token)

    assert payload["exp"] - payload["iat"] == 1800


def test_create_access_token_extra_claims_and_reserved_protection():
    """Verifies that extra claims are included but cannot overwrite reserved claims."""
    user_id = str(uuid.uuid4())
    extra = {
        "tenant_id": "campus_main",
        "sub": "attempted_override_id",  # Reserved: should be ignored
        "type": "refresh",  # Reserved: should be ignored
    }

    token = create_access_token(
        user_id=user_id,
        email="admin.demo@campusfix.local",
        role=UserRole.ADMINISTRATOR,
        extra_claims=extra,
    )
    payload = decode_access_token(token)

    assert payload["sub"] == user_id
    assert payload["type"] == TOKEN_TYPE_ACCESS
    assert payload["tenant_id"] == "campus_main"


def test_create_access_token_input_validation():
    """Verifies that invalid user_id, email, or role raise ValueError."""
    with pytest.raises(ValueError, match="user_id cannot be empty"):
        create_access_token(user_id="", email="test@campusfix.local", role="STUDENT")

    with pytest.raises(ValueError, match="email cannot be empty"):
        create_access_token(user_id=str(uuid.uuid4()), email="", role="STUDENT")

    with pytest.raises(ValueError, match="role cannot be empty"):
        create_access_token(user_id=str(uuid.uuid4()), email="test@campusfix.local", role="")


def test_decode_access_token_rejects_expired():
    """Verifies that expired tokens raise jwt.ExpiredSignatureError."""
    user_id = str(uuid.uuid4())
    # Create token already expired in the past
    token = create_access_token(
        user_id=user_id,
        email="student@campusfix.local",
        role=UserRole.STUDENT,
        expires_delta=timedelta(seconds=-10),
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_decode_access_token_rejects_invalid_signature():
    """Verifies that tokens signed with a different key raise jwt.InvalidSignatureError."""
    user_id = str(uuid.uuid4())
    token = create_access_token(
        user_id=user_id,
        email="student@campusfix.local",
        role=UserRole.STUDENT,
        secret_key="different_secret_key_used_to_forge_signature_0000",
    )

    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(token)


def test_decode_access_token_rejects_unsupported_algorithm():
    """Verifies that tokens encoded with unsupported algorithms are rejected."""
    payload = {
        "sub": str(uuid.uuid4()),
        "email": "student@campusfix.local",
        "role": "STUDENT",
        "type": TOKEN_TYPE_ACCESS,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp()),
    }
    # Encode with 'none' algorithm
    insecure_token = jwt.encode(payload, key="", algorithm="none")

    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_access_token(insecure_token)


def test_decode_access_token_rejects_missing_required_claims():
    """Verifies that tokens missing mandatory claims raise MissingRequiredClaimError."""
    now = datetime.now(UTC)
    base_payload = {
        "sub": str(uuid.uuid4()),
        "email": "student@campusfix.local",
        "role": "STUDENT",
        "type": TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }

    for missing_claim in ("sub", "email", "role", "type"):
        incomplete_payload = dict(base_payload)
        del incomplete_payload[missing_claim]
        token = jwt.encode(incomplete_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        with pytest.raises(jwt.MissingRequiredClaimError):
            decode_access_token(token)


def test_decode_access_token_rejects_invalid_token_type():
    """Verifies that tokens with non-access type raise jwt.InvalidTokenError."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "email": "student@campusfix.local",
        "role": "STUDENT",
        "type": "refresh_token",  # Invalid type for access token endpoint
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    with pytest.raises(jwt.InvalidTokenError, match="Invalid token type"):
        decode_access_token(token)


def test_decode_access_token_rejects_malformed_token():
    """Verifies that malformed or non-string tokens raise jwt.DecodeError."""
    with pytest.raises(jwt.DecodeError):
        decode_access_token("not.a.valid.jwt.token")

    with pytest.raises(jwt.DecodeError):
        decode_access_token("")

    with pytest.raises(jwt.DecodeError):
        decode_access_token(None)  # type: ignore[arg-type]
