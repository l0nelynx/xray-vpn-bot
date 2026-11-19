"""Deliver confirmed web purchases independently of payment and subscription delivery."""
from __future__ import annotations

import asyncio
import logging
import math
import re
import time

import aiohttp
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError

from common_db.models import Transaction, WebAnalyticsPurchase
from common_db.runtime_config import apply_integrations_to_mapping

logger = logging.getLogger(__name__)
COLLECT_URL = "https://www.google-analytics.com/mp/collect"
# Keep terminal rows inspectable while excluding them from the due-time index scan.
END_OF_YEAR_9999 = 253402300799


class AnalyticsContext(BaseModel):
    client_id: str = Field(pattern=r"^[0-9]+\.[0-9]+$", max_length=80)
    session_id: str = Field(pattern=r"^[1-9][0-9]*$", max_length=18)


def settings() -> tuple[str, str]:
    config = apply_integrations_to_mapping({})
    measurement_id = config.get("ga4_measurement_id")
    secret = config.get("ga4_api_secret")
    if not isinstance(measurement_id, str) or not isinstance(secret, str):
        return "", ""
    if not re.fullmatch(r"G-[A-Z0-9]+", measurement_id) or not secret.strip():
        return "", ""
    return measurement_id, secret


async def enqueue(session, context: AnalyticsContext | None, transaction_id: str, provider: str):
    if context is None or not settings()[0]:
        return
    # Flush the invoice outside the savepoint so its own errors propagate.
    await session.flush()
    try:
        async with session.begin_nested():
            session.add(WebAnalyticsPurchase(
                transaction_id=transaction_id,
                payload={**context.model_dump(), "payment_provider": provider},
            ))
    except SQLAlchemyError:
        logger.warning("Could not queue GA4 purchase for transaction %s", transaction_id)


def purchase_payload(row: WebAnalyticsPurchase, tx: Transaction) -> dict | None:
    context = row.payload
    # Earlier outbox writers stored a full invoice-time event in this JSON column.
    # Read only attribution and the invoice currency that older transactions lack.
    params = context["events"][0]["params"] if "events" in context else context
    currency = tx.currency or params.get("currency")
    amount = tx.amount
    if not currency or amount is None or not math.isfinite(amount) or amount <= 0:
        return None
    tariff = f"sid:{tx.squad_id}:esid:{tx.external_squad_id}"
    item = {"item_id": f"{tariff}:{tx.days_ordered}", "item_name": tariff,
            "item_variant": str(tx.days_ordered), "quantity": 1}
    purchase = {
        "transaction_id": tx.transaction_id,
        "session_id": int(params["session_id"]),
        "engagement_time_msec": 1,
        "payment_provider": params["payment_provider"],
        "payment_type": tx.payment_method,
        "purchase_kind": "renewal" if tx.target_rw_id is not None else "new",
        "items": [item],
    }
    if params["payment_provider"] == "crypto":
        # CryptoPay invoices are denominated in tokens. GA4 revenue requires
        # ISO 4217, and the transaction has no verified fiat equivalent.
        purchase.update(payment_asset=currency, payment_amount=amount)
    else:
        purchase.update(currency=currency, value=amount)
        item["price"] = amount
    return {
        "client_id": context["client_id"],
        "timestamp_micros": int(row.confirmed_at * 1_000_000),
        "events": [{"name": "purchase", "params": purchase}],
    }


async def _send(client, credentials: dict, payload: dict) -> str | None:
    try:
        async with client.post(
            COLLECT_URL, params=credentials, json=payload, allow_redirects=False,
        ) as response:
            return None if 200 <= response.status < 300 else f"http_{response.status}"
    except (aiohttp.ClientError, TimeoutError):
        # Exception messages may contain the secret-bearing URL.
        return "network_error"


async def send_batch(session_factory, client, measurement_id: str, secret: str) -> int:
    credentials = {"measurement_id": measurement_id, "api_secret": secret}
    count = 0
    for _ in range(25):
        now = time.time()
        eligible = (
            select(WebAnalyticsPurchase.transaction_id)
            .join(Transaction, Transaction.transaction_id == WebAnalyticsPurchase.transaction_id)
            .where(
                Transaction.purchase_source == "web",
                func.coalesce(Transaction.payment_confirmed_at, WebAnalyticsPurchase.confirmed_at).is_not(None),
                WebAnalyticsPurchase.sent_at.is_(None),
                WebAnalyticsPurchase.next_attempt_at <= now,
            )
            .order_by(WebAnalyticsPurchase.next_attempt_at, WebAnalyticsPurchase.transaction_id)
            .limit(1).with_for_update(skip_locked=True, of=WebAnalyticsPurchase)
        )
        # Reserve with one write (also atomic on SQLite). Commit before HTTP so
        # a slow collector cannot hold a database lock during payment delivery.
        async with session_factory.begin() as session:
            row = await session.scalar(
                update(WebAnalyticsPurchase)
                .where(WebAnalyticsPurchase.transaction_id == eligible.scalar_subquery())
                .values(next_attempt_at=now + 60)
                .returning(WebAnalyticsPurchase)
            )
            if row is None:
                break
            tx_id = row.transaction_id
            tx = await session.get(Transaction, tx_id)
            row.confirmed_at = row.confirmed_at or tx.payment_confirmed_at
            if now - row.confirmed_at > 71 * 3600:
                row.last_error = "expired"
                row.next_attempt_at = END_OF_YEAR_9999
                continue
            try:
                payload = purchase_payload(row, tx)
            except (ValueError, IndexError, KeyError, TypeError):
                payload = None
            if payload is None:
                row.last_error = "invalid_purchase"
                row.next_attempt_at = END_OF_YEAR_9999
                continue
            row.attempts += 1
            attempt = row.attempts

        error = await _send(client, credentials, payload)
        if error is None:
            outcome = {"sent_at": time.time(), "last_error": None}
        else:
            delay = min(3600, 30 * 2 ** min(attempt, 7))
            outcome = {"next_attempt_at": time.time() + delay, "last_error": error}
            logger.warning("GA4 delivery failed tx=%s error=%s", tx_id, error)
        async with session_factory.begin() as session:
            result = await session.execute(
                update(WebAnalyticsPurchase)
                .where(WebAnalyticsPurchase.transaction_id == tx_id, WebAnalyticsPurchase.attempts == attempt)
                .values(**outcome)
            )
            if error is None and result.rowcount:
                count += 1
    return count


async def delivery_loop(session_factory):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as client:
        while True:
            try:
                measurement_id, secret = settings()
                if measurement_id:
                    await send_batch(session_factory, client, measurement_id, secret)
            except Exception:
                logger.error("GA4 outbox iteration failed")
            await asyncio.sleep(15)
