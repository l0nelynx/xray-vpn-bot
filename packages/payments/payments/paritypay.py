import logging

import aiohttp

from .base import Invoice, InvoiceRequest, PaymentError, PaymentProvider
from .config import get_config
from .signatures import sign_paritypay_request

logger = logging.getLogger(__name__)

_VALID_SERVICES = {"card", "sbp"}


def _resolve_service(requested: str | None) -> str:
    """Use the per-button service when set & valid (card/sbp), else the config
    default. Mirrors Platega's `_resolve_method`."""
    if requested and requested.lower() in _VALID_SERVICES:
        return requested.lower()
    if requested and requested.lower() != "default":
        logger.warning("ParityPay: ignoring unknown service %r", requested)
    default = (get_config().paritypay_service or "sbp").lower()
    return default if default in _VALID_SERVICES else "sbp"


def _fmt_amount(amount: float) -> object:
    """Serialize the amount identically in the JSON body and the signed string:
    whole numbers as int (``149``), otherwise rounded to 2 decimals (``149.5``).
    Keeping one representation avoids float/int signature mismatches."""
    rounded = round(float(amount), 2)
    return int(rounded) if rounded == int(rounded) else rounded


class ParityPayProvider(PaymentProvider):
    """ParityPay (paritypay.ru) payment gateway — invoice/payment side only."""

    name = "paritypay"
    payment_method = "PARITYPAY"
    supported_currencies = ("RUB",)

    _session: aiohttp.ClientSession | None = None

    @classmethod
    def _get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession()
        return cls._session

    async def create_invoice(self, request: InvoiceRequest) -> Invoice:
        cfg = get_config()
        shop_id = cfg.paritypay_shop_id
        secret1 = cfg.paritypay_secret_1
        api_url = cfg.paritypay_url

        if not (shop_id and secret1 and api_url):
            raise PaymentError("ParityPay is not configured")

        service = _resolve_service(request.method)

        # Flat body: every value is a scalar, so the signature is a simple
        # sorted-key value concat. The signature is computed over exactly this
        # body, so the provider's server-side re-sign matches.
        body: dict = {
            "shop_id": shop_id,
            "amount": _fmt_amount(request.amount),
            "order_id": request.transaction_id,
            "service": service,
            "comment": request.description or f"TgId:{request.user_tg_id}",
        }
        # Prefer a per-request callback so we don't depend on cassa settings.
        if cfg.paritypay_webhook:
            body["callback_url"] = cfg.paritypay_webhook

        headers = {
            "Content-Type": "application/json",
            "X-SIGNATURE": sign_paritypay_request(body, secret1),
        }

        try:
            async with self._get_session().post(
                f"{api_url.rstrip('/')}/invoice/create",
                json=body,
                headers=headers,
            ) as response:
                text = await response.text()
                if response.status != 200:
                    raise PaymentError(f"ParityPay HTTP {response.status}: {text}")
                data = await response.json()
        except aiohttp.ClientError as e:
            raise PaymentError(f"ParityPay HTTP error: {e}") from e

        if isinstance(data, dict) and data.get("error"):
            raise PaymentError(f"ParityPay error: {data['error']}")

        invoice_id = data.get("id")
        url = data.get("link")
        if not invoice_id or not url:
            raise PaymentError(f"ParityPay response incomplete: {data}")

        return Invoice(
            provider=self.name,
            invoice_id=str(invoice_id),
            url=url,
            amount=float(request.amount),
            currency=request.currency.upper(),
            raw=data,
        )
