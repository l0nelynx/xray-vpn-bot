"""Stateless Telegram navigation and payment flow for Tariff Constructor."""
from __future__ import annotations

import logging
import uuid

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    WebAppInfo,
)
from payments import (
    InvoiceRequest,
    PaymentError,
    available_providers,
    create_invoice,
    validate_provider_invoice,
)
from payments.stars import validate_stars_payment

import app.database.requests as rq
from app.api.handlers import payment_process_background
from app.bot_constructor.feature import is_enabled
from app.database.models import async_session
from app.locale.utils import get_user_lang
from app.notify_log import esc, notify_log
from app.settings import bot, secrets
from common_db.repo.webapp_menu import (
    get_active_node,
    invoice_target,
    list_nodes,
    localized_text,
)

logger = logging.getLogger(__name__)
router = Router()


def _allowed_providers() -> set[str]:
    return {
        provider.name
        for provider in available_providers()
        if "bot" in provider.surfaces
    }


def _target_for_bot(node):
    target = invoice_target(node, allowed_providers=_allowed_providers())
    if target is None:
        return None
    try:
        validate_provider_invoice(
            target.provider,
            currency=target.currency,
            method=target.method,
            surface="bot",
        )
    except PaymentError:
        return None
    return target


async def _miniapp_fallback(callback: CallbackQuery) -> None:
    lang = await get_user_lang(callback.from_user.id)
    url = secrets.get("miniapp_url")
    keyboard = (
        InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text=lang.btn_open_app, web_app=WebAppInfo(url=url))
            ]]
        )
        if url
        else None
    )
    await callback.message.edit_text(
        lang.text_pay_method,
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await callback.answer()


async def _render_level(callback: CallbackQuery, parent_id: int | None) -> None:
    lang_code = await rq.get_user_language(callback.from_user.id) or "ru"
    lang = await get_user_lang(callback.from_user.id)
    async with async_session() as session:
        nodes = await list_nodes(session)
        parent = (
            await get_active_node(session, parent_id)
            if parent_id is not None
            else None
        )
    if parent_id is not None and (parent is None or parent.action != "buttons"):
        await callback.answer(lang.msg_plan_not_found, show_alert=True)
        return

    children = sorted(
        (
            node
            for node in nodes
            if node.parent_id == parent_id and node.is_active
        ),
        key=lambda node: (node.sort_order, node.id),
    )
    rows: list[list[InlineKeyboardButton]] = []
    for node in children:
        target = _target_for_bot(node)
        if node.action == "invoice" and target is None:
            continue
        if node.action == "buttons":
            has_visible_child = any(
                child.parent_id == node.id
                and child.is_active
                and (
                    child.action == "buttons"
                    or _target_for_bot(child) is not None
                )
                for child in nodes
            )
            if not has_visible_child:
                continue
        label = localized_text(node, lang_code)
        if target is not None:
            amount = f"{target.amount:.2f}".rstrip("0").rstrip(".")
            label = f"{label} · {amount} {target.currency}"
        rows.append([
            InlineKeyboardButton(text=label, callback_data=f"tariff:node:{node.id}")
        ])

    if parent is not None:
        back_callback = (
            f"tariff:node:{parent.parent_id}"
            if parent.parent_id is not None
            else "tariff:root"
        )
        rows.append([InlineKeyboardButton(text=lang.btn_back, callback_data=back_callback)])
    rows.append([InlineKeyboardButton(text=lang.btn_to_main, callback_data="Main")])
    text = localized_text(parent, lang_code) if parent else lang.text_pay_method
    if not rows[:-1]:
        await callback.answer(lang.msg_plan_not_found, show_alert=True)
        return
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


async def _create_payment(callback: CallbackQuery, node_id: int) -> None:
    lang = await get_user_lang(callback.from_user.id)
    async with async_session() as session:
        node = await get_active_node(session, node_id)
    if node is None:
        await callback.answer(lang.msg_plan_not_found, show_alert=True)
        return
    target = _target_for_bot(node)
    if target is None:
        await callback.answer(lang.msg_plan_not_found, show_alert=True)
        return
    try:
        provider = validate_provider_invoice(
            target.provider,
            currency=target.currency,
            method=target.method,
            surface="bot",
        )
    except PaymentError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    transaction_id = str(uuid.uuid4())
    if target.provider == "stars":
        tx = await rq.create_transaction(
            user_tg_id=callback.from_user.id,
            user_transaction=transaction_id,
            provider_invoice_id=transaction_id,
            username=callback.from_user.username,
            days=target.days,
            payment_method=provider.payment_method,
            amount=target.amount,
            squad_id=target.squad_id,
            internal_squad_ids=list(target.internal_squad_ids),
            external_squad_id=target.external_squad_id,
            traffic_limit_bytes=target.traffic_limit_bytes,
            traffic_limit_strategy=target.traffic_limit_strategy,
            remnawave_description=target.remnawave_description,
            remnawave_tag=target.remnawave_tag,
        )
        if tx is None:
            await callback.answer("User not found", show_alert=True)
            return
        amount = int(target.amount)
        try:
            await bot.send_invoice(
                callback.from_user.id,
                title=localized_text(
                    node,
                    await rq.get_user_language(callback.from_user.id) or "ru",
                ),
                description=lang.msg_invoice_description.format(amount=amount),
                payload=transaction_id,
                currency="XTR",
                prices=[LabeledPrice(label="VPN", amount=amount)],
                provider_token="",
            )
        except Exception as exc:
            logger.exception("Telegram Stars invoice send failed")
            await rq.update_order_status(transaction_id, "failed")
            await callback.answer(str(exc), show_alert=True)
            return
        await callback.answer(lang.msg_pay_in_stars)
    else:
        try:
            invoice = await create_invoice(
                target.provider,
                InvoiceRequest(
                    transaction_id=transaction_id,
                    amount=target.amount,
                    currency=target.currency,
                    days=target.days,
                    user_tg_id=callback.from_user.id,
                    username=callback.from_user.username,
                    description=localized_text(
                        node,
                        await rq.get_user_language(callback.from_user.id) or "ru",
                    ),
                    method=target.method,
                ),
            )
        except PaymentError as exc:
            logger.warning("Bot invoice failed for node %s: %s", node_id, exc)
            await callback.answer(str(exc), show_alert=True)
            return
        tx = await rq.create_transaction(
            user_tg_id=callback.from_user.id,
            user_transaction=transaction_id,
            provider_invoice_id=invoice.invoice_id,
            username=callback.from_user.username,
            days=target.days,
            payment_method=provider.payment_method,
            amount=target.amount,
            squad_id=target.squad_id,
            internal_squad_ids=list(target.internal_squad_ids),
            external_squad_id=target.external_squad_id,
            traffic_limit_bytes=target.traffic_limit_bytes,
            traffic_limit_strategy=target.traffic_limit_strategy,
            remnawave_description=target.remnawave_description,
            remnawave_tag=target.remnawave_tag,
        )
        if tx is None:
            await callback.answer("User not found", show_alert=True)
            return
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=lang.btn_open, url=invoice.url)],
                [InlineKeyboardButton(text=lang.btn_back, callback_data=f"tariff:node:{node.parent_id}")
                 if node.parent_id is not None else InlineKeyboardButton(
                     text=lang.btn_back, callback_data="tariff:root"
                 )],
                [InlineKeyboardButton(text=lang.btn_to_main, callback_data="Main")],
            ]
        )
        await callback.message.edit_text(
            lang.msg_pay_link.format(link=invoice.url),
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        await callback.answer()

    await notify_log(
        f"🧾 <b>Invoice created (bot tree)</b>\n"
        f"user: <code>{callback.from_user.id}</code> "
        f"@{esc(callback.from_user.username or '—')}\n"
        f"provider: <code>{esc(target.provider)}</code>\n"
        f"node: <code>{node_id}</code>\n"
        f"amount: <code>{target.amount} {esc(target.currency)}</code>\n"
        f"tx: <code>{transaction_id}</code>"
    )


@router.callback_query(F.data.in_({"Premium", "Extend_Month", "tariff:root"}))
async def tariff_root(callback: CallbackQuery) -> None:
    if not await is_enabled():
        await _miniapp_fallback(callback)
        return
    await _render_level(callback, None)


@router.callback_query(F.data.startswith("tariff:node:"))
async def tariff_node(callback: CallbackQuery) -> None:
    if not await is_enabled():
        await _miniapp_fallback(callback)
        return
    try:
        node_id = int(callback.data.rsplit(":", 1)[1])
    except (TypeError, ValueError):
        await callback.answer("Invalid menu node", show_alert=True)
        return
    async with async_session() as session:
        node = await get_active_node(session, node_id)
    if node is None:
        await callback.answer("Menu item is unavailable", show_alert=True)
    elif node.action == "buttons":
        await _render_level(callback, node.id)
    else:
        await _create_payment(callback, node.id)


@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery) -> None:
    tx = await rq.get_full_transaction_info(query.invoice_payload)
    valid = validate_stars_payment(
        tx,
        user_tg_id=query.from_user.id,
        currency=query.currency,
        total_amount=query.total_amount,
    )
    await query.answer(ok=valid, error_message=None if valid else "Invoice is no longer valid")


@router.message(F.successful_payment)
async def success_stars_payment_handler(message: Message) -> None:
    payment = message.successful_payment
    tx = await rq.get_full_transaction_info(payment.invoice_payload)
    if not validate_stars_payment(
        tx,
        user_tg_id=message.from_user.id,
        currency=payment.currency,
        total_amount=payment.total_amount,
    ):
        logger.error("Rejected mismatched Stars payment %s", payment.invoice_payload)
        return
    await payment_process_background(tx["transaction_id"])
