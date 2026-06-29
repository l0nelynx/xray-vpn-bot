"""Password hashing + JWT helpers for the Android API.

argon2id for password storage, HS256 JWT for stateless access tokens. Refresh
tokens are opaque random strings hashed (sha256) before storage; the client
keeps the raw value and presents it on /refresh.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError, VerificationError

from ..config import (
    get_android_access_ttl_seconds,
    get_android_jwt_issuer,
    get_android_jwt_secret,
    get_android_refresh_ttl_seconds,
)

_PH = PasswordHasher()
_REFRESH_TOKEN_BYTES = 48  # 64 chars urlsafe-b64

# Single dummy hash used to pace requests on missing-account paths so the
# response time of /login does not leak whether an email exists.
_DUMMY_HASH = _PH.hash("xray-vpn-bot/dummy/never-matches")


def hash_password(plaintext: str) -> str:
    return _PH.hash(plaintext)


def verify_password(stored_hash: str | None, plaintext: str) -> bool:
    """Constant-time check; returns False on missing or invalid hashes."""
    target = stored_hash or _DUMMY_HASH
    try:
        _PH.verify(target, plaintext)
        return stored_hash is not None
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _PH.check_needs_rehash(stored_hash)


# --- JWT ---


@dataclass
class AccessClaims:
    user_id: int
    jti: str
    issued_at: int
    expires_at: int


class JWTError(Exception):
    pass


def _require_secret() -> str:
    secret = get_android_jwt_secret()
    if not secret:
        raise JWTError("android_jwt_secret is not configured")
    if len(secret.encode("utf-8")) < 32:
        raise JWTError(
            "android_jwt_secret must be at least 32 bytes (HS256 / RFC 7518 §3.2)"
        )
    return secret


def issue_access_token(user_id: int) -> tuple[str, AccessClaims]:
    now = int(time.time())
    ttl = get_android_access_ttl_seconds()
    claims = AccessClaims(
        user_id=user_id,
        jti=uuid.uuid4().hex,
        issued_at=now,
        expires_at=now + ttl,
    )
    payload = {
        "iss": get_android_jwt_issuer(),
        "sub": str(user_id),
        "iat": claims.issued_at,
        "exp": claims.expires_at,
        "jti": claims.jti,
        "typ": "access",
    }
    token = jwt.encode(payload, _require_secret(), algorithm="HS256")
    return token, claims


def decode_access_token(token: str) -> AccessClaims:
    try:
        payload = jwt.decode(
            token,
            _require_secret(),
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub", "jti"]},
            issuer=get_android_jwt_issuer(),
        )
    except jwt.ExpiredSignatureError as exc:
        raise JWTError("token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise JWTError("invalid token") from exc
    if payload.get("typ") != "access":
        raise JWTError("wrong token type")
    try:
        return AccessClaims(
            user_id=int(payload["sub"]),
            jti=payload["jti"],
            issued_at=int(payload["iat"]),
            expires_at=int(payload["exp"]),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise JWTError("malformed token") from exc


# --- Refresh tokens ---
#
# Layout: <family_id>.<random>. We store sha256(token) so DB compromise alone
# cannot let an attacker replay refreshes. family_id rides along so /refresh
# can locate the family without an extra round-trip.


def new_family_id() -> str:
    return uuid.uuid4().hex


def issue_refresh_token(family_id: str) -> tuple[str, str]:
    raw = f"{family_id}.{secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)}"
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def split_family_id(raw_token: str) -> str | None:
    head, sep, _ = raw_token.partition(".")
    if not sep or not head:
        return None
    # family_id is 32-hex chars (uuid4().hex)
    if len(head) != 32 or not all(c in "0123456789abcdef" for c in head):
        return None
    return head


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def refresh_ttl_seconds() -> int:
    return get_android_refresh_ttl_seconds()


def access_ttl_seconds() -> int:
    return get_android_access_ttl_seconds()


def jwt_payload_meta() -> dict[str, Any]:
    return {
        "issuer": get_android_jwt_issuer(),
        "access_ttl": access_ttl_seconds(),
        "refresh_ttl": refresh_ttl_seconds(),
    }


# --- One-time email codes ---------------------------------------------------


def new_email_code() -> str:
    """6-digit numeric code. secrets.randbelow gives uniform distribution
    even at the edge of the range (random.randint does not)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_email_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def constant_time_code_eq(stored_hash: str, presented_code: str) -> bool:
    return hmac.compare_digest(stored_hash, hash_email_code(presented_code))
