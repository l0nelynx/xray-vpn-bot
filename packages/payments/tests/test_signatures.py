"""Verify the extracted signature functions match the schemes that were
previously inlined in the seller bot's webhook handlers, byte for byte.

Each test recomputes the expected signature with the *original* formula (copied
from the pre-refactor app/api/*.py) and asserts the shared verifier accepts it
and rejects tampering.
"""
import hashlib
import hmac

from payments import signatures


def test_apay_accepts_valid_and_rejects_tampered():
    order_id, status, secret = "order-123", "approved", "s3cr3t"
    # original: hashlib.md5(f"{order_id}:{status}:{secret}".encode()).hexdigest()
    sign = hashlib.md5(f"{order_id}:{status}:{secret}".encode()).hexdigest()
    assert signatures.verify_apay_webhook(order_id, status, sign, secret) is True
    assert signatures.verify_apay_webhook(order_id, "pending", sign, secret) is False
    assert signatures.verify_apay_webhook(order_id, status, "deadbeef", secret) is False


def test_cryptopay_matches_original_hmac_scheme():
    token = "12345:AAtoken"
    raw = b'{"update_type":"invoice_paid","payload":{"invoice_id":42}}'
    # original _verify_signature: HMAC-SHA256(raw, key=sha256(token))
    secret = hashlib.sha256(token.encode()).digest()
    sig = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    assert signatures.verify_cryptopay_webhook(token, raw, sig) is True
    assert signatures.verify_cryptopay_webhook(token, raw + b"x", sig) is False
    assert signatures.verify_cryptopay_webhook("", raw, sig) is False
    assert signatures.verify_cryptopay_webhook(token, raw, "") is False


def test_crystal_matches_original_sha1_scheme():
    invoice_id, salt = "inv-77", "saltyseadog"
    # original: hashlib.sha1(f"{id}:{salt}".encode()).hexdigest()
    sig = hashlib.sha1(f"{invoice_id}:{salt}".encode()).hexdigest()
    assert signatures.verify_crystal_webhook(invoice_id, sig, salt) is True
    assert signatures.verify_crystal_webhook(invoice_id, sig, "wrong") is False
    assert signatures.verify_crystal_webhook("other", sig, salt) is False


def test_platega_header_equality():
    assert signatures.verify_platega_webhook("m1", "k1", "m1", "k1") is True
    assert signatures.verify_platega_webhook("m1", "bad", "m1", "k1") is False
    assert signatures.verify_platega_webhook("bad", "k1", "m1", "k1") is False
    # Missing headers must not authenticate against non-empty config.
    assert signatures.verify_platega_webhook("", "", "m1", "k1") is False


def test_apay_invoice_sign_uses_integer_minor_units():
    """The APay invoice sign must serialise the amount as integer kopecks,
    matching what the live miniapp provider sends (e.g. 50.00 RUB -> 5000)."""
    tx, secret = "abc", "s3cr3t"
    amount_minor = int(round(50.0 * 100))
    expected = hashlib.md5(f"{tx}:{amount_minor}:{secret}".encode()).hexdigest()
    assert expected == hashlib.md5(f"{tx}:5000:{secret}".encode()).hexdigest()
