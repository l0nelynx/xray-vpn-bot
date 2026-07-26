"""Encrypt payment credentials at rest (stdlib-only AEAD-style blob).

Format: ``v1$<salt_b64>$<nonce_b64>$<ciphertext_b64>$<mac_b64>``

Keystream = successive SHA-256(HMAC-SHA256(key, nonce || counter)).
MAC = HMAC-SHA256(key, salt || nonce || ciphertext).
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from typing import Any


_PREFIX = "v1"


def derive_key(secret: str) -> bytes:
    """Derive a 32-byte key from the bootstrap ``payments_secrets_key`` (or fallback)."""
    raw = (secret or "").encode("utf-8")
    if not raw:
        # Deterministic empty fallback — still needs a non-empty secret in prod.
        raw = b"xray-vpn-bot-payments-unconfigured"
    return hashlib.pbkdf2_hmac("sha256", raw, b"xray-payments-v1", 120_000, dklen=32)


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    try:
        decoded = base64.b64decode(data + pad, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid payment secret base64") from exc
    # Python's decoder accepts alternate non-zero padding bits that decode to
    # the same bytes. Reject non-canonical encodings so any textual mutation of
    # the authenticated blob is detected deterministically.
    if _b64e(decoded) != data:
        raise ValueError("non-canonical payment secret base64")
    return decoded


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(
            key,
            nonce + counter.to_bytes(4, "big"),
            hashlib.sha256,
        ).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def encrypt_json(payload: dict[str, Any], key: bytes) -> str:
    plain = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(16)
    # Mix salt into key material for this blob.
    blob_key = hashlib.sha256(key + salt).digest()
    stream = _keystream(blob_key, nonce, len(plain))
    cipher = bytes(a ^ b for a, b in zip(plain, stream))
    mac = hmac.new(blob_key, salt + nonce + cipher, hashlib.sha256).digest()
    return "$".join((_PREFIX, _b64e(salt), _b64e(nonce), _b64e(cipher), _b64e(mac)))


def decrypt_json(blob: str, key: bytes) -> dict[str, Any]:
    if not blob:
        return {}
    parts = blob.split("$")
    if len(parts) != 5 or parts[0] != _PREFIX:
        raise ValueError("unsupported payment secret blob format")
    salt, nonce, cipher, mac = map(_b64d, parts[1:])
    blob_key = hashlib.sha256(key + salt).digest()
    expected = hmac.new(blob_key, salt + nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, mac):
        raise ValueError("payment secret MAC mismatch")
    stream = _keystream(blob_key, nonce, len(cipher))
    plain = bytes(a ^ b for a, b in zip(cipher, stream))
    data = json.loads(plain.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("payment secret payload must be an object")
    return data
