"""Verified Heleket payment notifications for all checkout surfaces."""
from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation

from fastapi import BackgroundTasks, HTTPException, Request

import app.database.requests as rq
from app.api.handlers import payment_process_background
from app.settings import secrets
from payments import signatures

logger = logging.getLogger(__name__)


async def payment_webhook_handler(request: Request, background_tasks: BackgroundTasks):
    raw = await request.body()
    if not signatures.verify_heleket_webhook(raw, secrets.get("heleket_api_key") or ""):
        logger.warning("Heleket webhook: invalid signature or unconfigured provider")
        raise HTTPException(status_code=401, detail="invalid signature")

    data = json.loads(raw)  # The signature verifier has validated the JSON object.
    if data.get("type") != "payment" or data.get("status") not in ("paid", "paid_over"):
        return {"ok": True, "skipped": True}

    order_id = data.get("order_id")
    invoice_id = data.get("uuid")
    if not isinstance(order_id, str) or not order_id or not isinstance(invoice_id, str) or not invoice_id:
        raise HTTPException(status_code=400, detail="missing order_id or uuid")

    tx = await rq.get_full_transaction_info(order_id)
    if not tx:
        # A callback can race with the invoice transaction commit. Allow retry.
        raise HTTPException(status_code=404, detail="transaction not found")
    try:
        amount = Decimal(str(data.get("amount")))
        expected_amount = Decimal(str(tx.get("amount")))
    except InvalidOperation:
        raise HTTPException(status_code=400, detail="invalid amount")
    if (
        tx.get("transaction_id") != order_id
        or tx.get("payment_method") != "HELEKET"
        or tx.get("provider_invoice_id") != invoice_id
        or data.get("currency") != "USD"
        or not amount.is_finite()
        or amount <= 0
        or amount != expected_amount
    ):
        raise HTTPException(status_code=400, detail="invoice does not match transaction")

    # Delivery claims the local transaction atomically and skips delivered
    # orders, including repeated paid/paid_over callbacks for the same invoice.
    background_tasks.add_task(payment_process_background, order_id)
    return {"ok": True}
