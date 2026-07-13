import logging

from fastapi import BackgroundTasks, Request

from app.api.handlers import payment_process_background
from app.settings import secrets
from payments import signatures

logger = logging.getLogger(__name__)


async def payment_webhook_handler(request: Request, background_tasks: BackgroundTasks):
    """Handle POST /bot/paritypay_webhook callback from ParityPay.

    ParityPay signs the JSON body (sorted keys, concatenated values, HMAC-SHA256
    with secret key №2) and sends it in the ``X-SIGNATURE`` header; we re-sign
    the received body and compare. The webhook echoes our own ``order_id`` (the
    local transaction id), so delivery is dispatched on ``order_id`` — unlike
    Platega, which reports back the provider's own id.

    We always answer HTTP 200 so ParityPay stops retrying (it retries up to 5
    times on any non-200); delivery only runs on a verified ``PAID`` event.
    """
    try:
        raw_data = await request.json()
    except Exception as e:
        logger.warning("ParityPay webhook: unreadable body: %s", e)
        return {"status": "error", "message": "invalid body"}

    if not signatures.verify_paritypay_webhook(
        raw_data if isinstance(raw_data, dict) else {},
        request.headers.get("X-SIGNATURE", ""),
        secrets.get("paritypay_secret_2", "") or "",
    ):
        logger.warning("ParityPay webhook: invalid signature")
        return {"status": "error", "message": "unauthorized"}

    logger.info(f"ParityPay webhook received: {raw_data}")
    order_id = raw_data.get("order_id")
    status = (raw_data.get("status") or "").upper()

    if not order_id:
        logger.warning("ParityPay webhook: missing order_id")
        return {"status": "error", "message": "missing order_id"}

    if status == "PAID":
        logger.info(f"ParityPay payment confirmed: order_id={order_id}")
        background_tasks.add_task(payment_process_background, order_id)
        return {"status": "success"}

    # NEW / EXPIRED / ERROR / REFUNDED — acknowledge so ParityPay stops retrying.
    logger.info(f"ParityPay payment status {status} for order_id={order_id}")
    return {"status": "received"}
