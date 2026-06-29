"""Pure webhook signature verification for the payment providers.

These functions encapsulate the exact signing schemes each gateway uses to
authenticate its callbacks. They were previously inlined in the seller bot's
webhook handlers (app/api/*.py); centralising them keeps every detail of a
provider's protocol in one place and makes them unit-testable without FastAPI.

All comparisons use :func:`hmac.compare_digest` to avoid timing leaks.
"""

import hashlib
import hmac


def verify_apay_webhook(order_id: str, status: str, sign: str, secret: str) -> bool:
    """APay: md5("<order_id>:<status>:<secret>"). Caller checks status first."""
    expected = hashlib.md5(f"{order_id}:{status}:{secret}".encode()).hexdigest()
    return hmac.compare_digest(sign, expected)


def verify_cryptopay_webhook(token: str, raw_body: bytes, signature: str) -> bool:
    """@CryptoBot: HMAC-SHA256 over the raw body, keyed by sha256(token).

    See https://help.crypt.bot/crypto-pay-api#webhook-updates
    """
    if not token or not signature:
        return False
    secret = hashlib.sha256(token.encode()).digest()
    digest = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def verify_crystal_webhook(invoice_id: str, signature: str, salt: str) -> bool:
    """CrystalPay: sha1("<invoice_id>:<salt>")."""
    expected = hashlib.sha1(f"{invoice_id}:{salt}".encode()).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_platega_webhook(
    merchant_id_header: str,
    secret_header: str,
    expected_merchant_id: str,
    expected_secret: str,
) -> bool:
    """Platega authenticates callbacks by echoing the merchant's own
    X-MerchantId / X-Secret headers; verify both match our configured values."""
    return (
        hmac.compare_digest(merchant_id_header or "", expected_merchant_id or "")
        and hmac.compare_digest(secret_header or "", expected_secret or "")
    )
