import hashlib
import hmac
import json

import pytest

from remnawave_client.webhooks import (
    extract_vless_uuid,
    is_torrent_block_report,
    parse_webhook,
    torrent_block_ip,
    torrent_block_minutes,
    verify_webhook_signature,
)

_SECRET = "test-webhook-secret-abc123"

_SAMPLE_PAYLOAD = {
    "scope": "torrent_blocker",
    "event": "torrent_blocker.report",
    "timestamp": "2026-03-07T16:02:50.564Z",
    "data": {
        "node": {},
        "user": {"uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"},
        "report": {
            "actionReport": {
                "blocked": True,
                "ip": "203.0.113.42",
                "blockDuration": 1800,
                "willUnblockAt": "2026-03-07T16:32:48.986Z",
                "userId": "2",
                "processedAt": "2026-03-07T16:02:48.986Z",
            },
            "xrayReport": {
                "email": "2",
                "protocol": "bittorrent",
                "network": "tcp",
            },
        },
    },
}


def _sign(body: bytes, secret: str = _SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_verify_webhook_signature_valid():
    body = json.dumps(_SAMPLE_PAYLOAD, separators=(",", ":")).encode()
    assert verify_webhook_signature(body, _sign(body), _SECRET) is True


def test_verify_webhook_signature_invalid_secret():
    body = json.dumps(_SAMPLE_PAYLOAD, separators=(",", ":")).encode()
    assert verify_webhook_signature(body, _sign(body), "wrong") is False


def test_verify_webhook_signature_tampered_body():
    body = json.dumps(_SAMPLE_PAYLOAD, separators=(",", ":")).encode()
    sig = _sign(body)
    assert verify_webhook_signature(body + b"x", sig, _SECRET) is False


def test_verify_webhook_signature_empty_secret():
    body = json.dumps(_SAMPLE_PAYLOAD).encode()
    assert verify_webhook_signature(body, _sign(body), "") is False


def test_parse_torrent_block_payload():
    body = json.dumps(_SAMPLE_PAYLOAD).encode()
    payload = parse_webhook(body)
    assert payload.scope == "torrent_blocker"
    assert payload.event == "torrent_blocker.report"
    assert is_torrent_block_report(payload) is True


def test_extract_vless_uuid():
    body = json.dumps(_SAMPLE_PAYLOAD).encode()
    payload = parse_webhook(body)
    assert extract_vless_uuid(payload) == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def test_extract_vless_uuid_missing_user():
    payload_data = {**_SAMPLE_PAYLOAD, "data": {"node": {}, "user": {}, "report": {}}}
    payload = parse_webhook(json.dumps(payload_data).encode())
    assert extract_vless_uuid(payload) is None


def test_torrent_block_minutes():
    body = json.dumps(_SAMPLE_PAYLOAD).encode()
    payload = parse_webhook(body)
    assert torrent_block_minutes(payload) == 30


def test_torrent_block_minutes_minimum_one():
    data = json.loads(json.dumps(_SAMPLE_PAYLOAD))
    data["data"]["report"]["actionReport"]["blockDuration"] = 30
    payload = parse_webhook(json.dumps(data).encode())
    assert torrent_block_minutes(payload) == 1


def test_torrent_block_ip():
    body = json.dumps(_SAMPLE_PAYLOAD).encode()
    payload = parse_webhook(body)
    assert torrent_block_ip(payload) == "203.0.113.42"


def test_is_torrent_block_report_not_blocked():
    data = json.loads(json.dumps(_SAMPLE_PAYLOAD))
    data["data"]["report"]["actionReport"]["blocked"] = False
    payload = parse_webhook(json.dumps(data).encode())
    assert is_torrent_block_report(payload) is False


def test_is_torrent_block_report_wrong_scope():
    data = {**_SAMPLE_PAYLOAD, "scope": "user", "event": "user.created"}
    payload = parse_webhook(json.dumps(data).encode())
    assert is_torrent_block_report(payload) is False
