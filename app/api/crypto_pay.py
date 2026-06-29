"""@CryptoBot webhook handler.

Receives `invoice_paid` updates and triggers the unified subscription delivery
pipeline for invoices that were created by the miniapp / tariff constructor.

@CryptoBot delivers webhooks signed with HMAC-SHA256 using the bot token as the
key (sha256 of token, then HMAC over the raw JSON body).
See: https://help.crypt.bot/crypto-pay-api#webhook-updates
"""

import hashlib
import hmac
import json
import logging

from fastapi import BackgroundTasks, HTTPException, Request

import app.database.requests as rq
from app.api.handlers import payment_process_background
from app.settings import secrets

logger = logging.getLogger(__name__)


def _verify_signature(token: str, raw_body: bytes, signature: str) -> bool:
    if not token or not signature:
        return False
    secret = hashlib.sha256(token.encode()).digest()
    digest = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


async def cryptopay_webhook_handler(
    request: Request,
    background_tasks: BackgroundTasks,
):
    raw = await request.body()
    signature = request.headers.get("Crypto-Pay-Api-Signature", "")
    token = secrets.get("crypto_bot_token") or ""

    if not _verify_signature(token, raw, signature):
        logger.warning("CryptoPay webhook: invalid signature")
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON")

    if body.get("update_type") != "invoice_paid":
        return {"ok": True, "skipped": True}

    payload = body.get("payload") or {}
    invoice_id = payload.get("invoice_id")
    if invoice_id is None:
        raise HTTPException(status_code=400, detail="missing invoice_id")

    # Look up the transaction by invoice id (CryptoPay invoice id is stored as
    # the transaction_id for miniapp-originated payments).
    tx = await rq.get_full_transaction_info(str(invoice_id))
    if not tx:
        # Not ours (likely created via in-bot flow which is handled by aiosend
        # polling). Acknowledge so @CryptoBot does not retry.
        logger.info("CryptoPay webhook: unknown invoice %s, ignoring", invoice_id)
        return {"ok": True, "skipped": True}

    if tx.get("status") != "created":
        logger.info(
            "CryptoPay webhook: invoice %s already processed (status=%s)",
            invoice_id, tx.get("status"),
        )
        return {"ok": True, "skipped": True}

    background_tasks.add_task(payment_process_background, str(invoice_id))
    return {"ok": True}
