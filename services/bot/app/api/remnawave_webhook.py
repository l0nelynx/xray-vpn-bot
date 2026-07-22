"""Handle POST /bot/remnawave_webhook callbacks from the Remnawave panel."""

from __future__ import annotations

import logging

from fastapi import BackgroundTasks, Request
from fastapi.responses import JSONResponse

from app.api.crm_webhook_queue import enqueue_crm_webhook
from app.settings import secrets
from remnawave_client.webhooks import (
    parse_webhook,
    verify_webhook_signature,
)

logger = logging.getLogger(__name__)


async def _enqueue_payload(payload_dict: dict) -> None:
    ok = await enqueue_crm_webhook(payload_dict)
    if not ok:
        logger.error(
            "Remnawave webhook: failed to enqueue scope=%s event=%s",
            payload_dict.get("scope"),
            payload_dict.get("event"),
        )
    else:
        logger.info(
            "Remnawave webhook enqueued scope=%s event=%s",
            payload_dict.get("scope"),
            payload_dict.get("event"),
        )


async def remnawave_webhook_handler(
    request: Request, background_tasks: BackgroundTasks
):
    """Verify signature, ack quickly, enqueue CRM webhook job."""
    raw = await request.body()
    signature = request.headers.get("X-Remnawave-Signature", "")
    secret = secrets.get("remnawave_webhook_secret", "") or ""

    if not verify_webhook_signature(raw, signature, secret):
        logger.warning("Remnawave webhook: invalid signature")
        return JSONResponse(
            {"status": "error", "message": "unauthorized"},
            status_code=401,
        )

    try:
        payload = parse_webhook(raw)
    except Exception as exc:
        logger.warning("Remnawave webhook: invalid payload: %s", exc)
        return JSONResponse(
            {"status": "error", "message": "invalid payload"},
            status_code=400,
        )

    payload_dict = payload.model_dump(mode="json", by_alias=True)
    background_tasks.add_task(_enqueue_payload, payload_dict)

    return {"status": "received"}
