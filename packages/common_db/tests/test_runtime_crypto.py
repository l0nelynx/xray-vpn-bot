"""Tests for payment credential encryption helpers."""
from __future__ import annotations

from common_db.runtime_config.crypto import decrypt_json, derive_key, encrypt_json


def test_encrypt_roundtrip():
    key = derive_key("test-secret")
    payload = {"crypto_bot_token": "abc", "platega_payment_method": 2}
    blob = encrypt_json(payload, key)
    assert blob.startswith("v1$")
    assert decrypt_json(blob, key) == payload


def test_mac_rejects_tamper():
    key = derive_key("test-secret")
    blob = encrypt_json({"a": 1}, key)
    parts = blob.split("$")
    parts[3] = parts[3][:-1] + ("A" if parts[3][-1] != "A" else "B")
    tampered = "$".join(parts)
    try:
        decrypt_json(tampered, key)
        assert False, "expected ValueError"
    except ValueError:
        pass
