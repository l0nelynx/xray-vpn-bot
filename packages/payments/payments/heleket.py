"""Hosted crypto checkout through the official Heleket Python SDK."""
from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation

import requests
from heleket_sdk import ClientOptions, HeleketError, HeleketPayment, RequestsTransport
from heleket_sdk.types import CreateInvoiceRequest, Invoice as HeleketInvoice

from .base import Invoice, InvoiceRequest, PaymentError, PaymentProvider
from .config import PaymentsConfig, get_config


class HeleketProvider(PaymentProvider):
    name = "heleket"
    payment_method = "HELEKET"
    # Prices are denominated in USD; the payer chooses crypto at checkout.
    # One accounting currency also keeps transaction revenue reporting exact.
    supported_currencies = ("USD",)
    methods = (("default", "Crypto"),)

    @staticmethod
    def _create_invoice(cfg: PaymentsConfig, request: CreateInvoiceRequest) -> HeleketInvoice:
        # The SDK is synchronous. Own and close its HTTP session per call so
        # credentials can change at runtime without retaining a stale client.
        with requests.Session() as session:
            client = HeleketPayment(
                merchant_id=cfg.heleket_merchant_id,
                api_key=cfg.heleket_api_key,
                options=ClientOptions(
                    timeout=30,
                    transport=RequestsTransport(session),
                ),
            )
            return client.create_invoice(request)

    async def create_invoice(self, request: InvoiceRequest) -> Invoice:
        cfg = get_config()
        if not (cfg.heleket_merchant_id and cfg.heleket_api_key and cfg.heleket_webhook):
            raise PaymentError("Heleket is not configured in Dashboard → System → Payments")
        currency = request.currency.upper()
        if not self.supports(currency):
            raise PaymentError(f"Heleket does not support currency '{currency}'")
        try:
            amount = Decimal(str(request.amount))
        except InvalidOperation as exc:
            raise PaymentError("Heleket amount must be positive and finite") from exc
        if not amount.is_finite() or amount <= 0:
            raise PaymentError("Heleket amount must be positive and finite")

        try:
            invoice = await asyncio.to_thread(
                self._create_invoice,
                cfg,
                CreateInvoiceRequest(
                    amount=format(amount, "f"),
                    currency=currency,
                    order_id=request.transaction_id,
                    url_callback=cfg.heleket_webhook,
                    payer_email=request.user_email,
                    lifetime=3600,
                    is_payment_multiple=False,
                    accuracy_payment_percent="0",
                ),
            )
        except (HeleketError, ValueError) as exc:
            # SDK errors may contain upstream response bodies; do not expose
            # those through public invoice endpoints or log credentials.
            raise PaymentError("Heleket invoice creation failed") from exc
        if not invoice.uuid or not invoice.url:
            raise PaymentError("Heleket returned an incomplete invoice")

        return Invoice(
            provider=self.name,
            invoice_id=invoice.uuid,
            url=invoice.url,
            amount=request.amount,
            currency=currency,
            raw=invoice.model_dump(mode="json", exclude_none=True),
        )
