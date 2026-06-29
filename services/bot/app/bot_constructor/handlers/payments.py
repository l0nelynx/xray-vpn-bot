"""In-bot tariff selection and inline payment flow (Stars / Crypto / SBP / CrystalPay)."""
import logging
import uuid

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import LabeledPrice, Message, CallbackQuery, PreCheckoutQuery

from aiosend.types import Invoice

from app.api.a_pay import create_sbp_link as apays_create_sbp_link
from app.api.crystal_pay import crystal_create_link
from app.handlers.tools import success_payment_handler
from app.handlers.subscription_service import deliver_subscription, SubscriptionType
from app.notify_log import esc, notify_log
from app.database.tariff_repository import get_tariff_slug_by_days
from app.locale.utils import get_user_lang
from app.keyboards.localized import get_to_main_localized
from app.bot_constructor.keyboards.payment_kb import get_pay_methods_localized
from app.bot_constructor.keyboards.tools import (
    PaymentCallbackData,
    OptimizedTariffKeyboard,
    create_tariff_keyboard,
    get_price_stars,
    get_price_crypto,
    get_sbp_price,
    payment_keyboard,
)
from app.bot_constructor.tariffs import get_tariffs_stars, get_tariffs_crypto, get_tariffs_sbp
from app.settings import bot, cp, secrets
import app.database.requests as rq
from common_db.repo import promos as rq_promos

router = Router()


def _promo_reason_text(lang, reason: str) -> str:
    mapping = {
        rq_promos.REASON_INVALID: lang.promo_invalid_text,
        rq_promos.REASON_OWN_CODE: lang.promo_own_code_text,
        rq_promos.REASON_ALREADY_USED: lang.promo_already_used_text,
        rq_promos.REASON_ACTIVE_EXISTS: lang.promo_active_exists_text,
        rq_promos.REASON_REFERRAL_ONLY_ONE: lang.promo_already_used_text,
        rq_promos.REASON_REFERRAL_NOT_NEW: lang.promo_referral_new_only_text,
    }
    return mapping.get(reason, lang.promo_invalid_text)


PAYMENT_METHOD_NAMES = {
    "stars": "TG_STARS",
    "crypto": "CRYPTOPAY",
    "SBP_APAY": "SBP_APAY",
    "CRYSTAL": "CRYSTAL_PAY",
}


class PaymentState(StatesGroup):
    PrePayment = State()
    PaymentMethod = State()
    PaymentTariff = State()
    PaymentInvoice = State()
    PostPayment = State()
    PromoInput = State()


@router.callback_query(F.data == "Premium")
async def premium(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer(lang.msg_buying_premium)
    show_promo = await rq.can_use_promo(callback.from_user.id)
    await callback.message.edit_text(
        text=lang.text_pay_method,
        parse_mode="HTML",
        reply_markup=get_pay_methods_localized(lang, show_promo=show_promo),
    )
    await state.set_state(PaymentState.PaymentMethod)


@router.callback_query(F.data == "Extend_Month")
async def premium_extend(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer(lang.msg_extending_premium)
    show_promo = await rq.can_use_promo(callback.from_user.id)
    await callback.message.edit_text(
        text=lang.text_extend_pay_method,
        parse_mode="HTML",
        reply_markup=get_pay_methods_localized(lang, show_promo=show_promo),
    )
    await state.set_state(PaymentState.PaymentMethod)


@router.callback_query(F.data == "Enter_Promo", PaymentState.PaymentMethod)
async def enter_promo(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(text=lang.promo_enter_text, parse_mode="HTML")
    await state.set_state(PaymentState.PromoInput)


@router.message(PaymentState.PromoInput)
async def process_promo_input(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    promo_code = message.text.strip().upper()
    tg_id = message.from_user.id

    result = await rq.redeem_promo_for_user(tg_id, promo_code)
    if not result.ok:
        reason_text = _promo_reason_text(lang, result.reason)
        show_promo = result.reason not in (
            rq_promos.REASON_ACTIVE_EXISTS,
            rq_promos.REASON_ALREADY_USED,
            rq_promos.REASON_REFERRAL_ONLY_ONE,
        )
        await message.answer(
            text=reason_text,
            parse_mode="HTML",
            reply_markup=get_pay_methods_localized(lang, show_promo=show_promo),
        )
        await state.set_state(PaymentState.PaymentMethod)
        return

    promo_discount = result.discount_percent
    await state.update_data(PromoDiscount=promo_discount, PromoCode=promo_code)
    await message.answer(
        text=lang.promo_success_text.format(discount=promo_discount),
        parse_mode="HTML",
        reply_markup=get_pay_methods_localized(lang, show_promo=False),
    )
    await state.set_state(PaymentState.PaymentMethod)


@router.callback_query(PaymentState.PaymentMethod)
async def stars_plan(callback: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    promo_discount = state_data.get("PromoDiscount", 0)
    lang_code = await rq.get_user_language(callback.from_user.id) or "ru"
    lang = await get_user_lang(callback.from_user.id)

    db_keyboards = {
        "Stars_Plans": ("stars", get_price_stars()),
        "Crypto_Plans": ("crypto", get_price_crypto()),
        "SBP_Plans": ("SBP", get_sbp_price()),
        "SBP_Apay": ("SBP_APAY", get_sbp_price()),
        "Crystal_plans": ("CRYSTAL", get_sbp_price()),
    }
    fallback_keyboards = {
        "Stars_Plans": lambda: create_tariff_keyboard(
            tariff=get_tariffs_stars(), method="stars", base_price=get_price_stars(), extra_discount=promo_discount
        ),
        "Crypto_Plans": lambda: create_tariff_keyboard(
            tariff=get_tariffs_crypto(), method="crypto", base_price=get_price_crypto(), extra_discount=promo_discount
        ),
        "SBP_Plans": lambda: create_tariff_keyboard(
            tariff=get_tariffs_sbp(), method="SBP", base_price=get_sbp_price(), extra_discount=promo_discount
        ),
        "SBP_Apay": lambda: create_tariff_keyboard(
            tariff=get_tariffs_sbp(), method="SBP_APAY", base_price=get_sbp_price(), extra_discount=promo_discount
        ),
        "Crystal_plans": lambda: create_tariff_keyboard(
            tariff=get_tariffs_sbp(), method="CRYSTAL", base_price=get_sbp_price(), extra_discount=promo_discount
        ),
    }

    keyboard = None
    db_info = db_keyboards.get(callback.data)
    if db_info:
        method, base_price = db_info
        keyboard = await OptimizedTariffKeyboard.from_db(
            method, base_price, extra_discount=promo_discount, lang=lang_code
        )
    if not keyboard:
        builder = fallback_keyboards.get(callback.data)
        if builder:
            keyboard = builder()

    if keyboard:
        await callback.message.edit_text(lang.msg_choose_tariff, reply_markup=keyboard)
        await state.set_state(PaymentState.PaymentTariff)
    else:
        logging.warning("Unrecognised payment method callback: %s", callback.data)


@router.callback_query(PaymentCallbackData.filter(F.tag == "data"), PaymentState.PaymentTariff)
async def invoice_handler(callback: CallbackQuery, callback_data: PaymentCallbackData, state: FSMContext):
    method = callback_data.method
    amount = callback_data.amount
    days = callback_data.days
    lang = await get_user_lang(callback.from_user.id)

    if method == "stars":
        await callback.answer(lang.msg_pay_in_stars)
        prices = [LabeledPrice(label="XTR", amount=int(round(amount)))]
        await bot.send_invoice(
            callback.from_user.id,
            title=lang.msg_invoice_title,
            description=lang.msg_invoice_description.format(amount=int(round(amount))),
            prices=prices,
            provider_token="",
            payload=f"{days}",
            currency="XTR",
            reply_markup=payment_keyboard(int(round(amount))),
        )
    elif method == "crypto":
        invoice = await cp.create_invoice(amount, "USDT", payload=f"{days}")
        await callback.message.edit_text(f"pay: {invoice.bot_invoice_url}")
        invoice.poll(message=callback)
        await state.clear()
        await state.set_state(PaymentState.PrePayment)
    elif method == "SBP_APAY":
        amount_kopecks = int(round(amount * 100))
        link = await apays_create_sbp_link(callback=callback, amount=amount_kopecks, days=days)
        await callback.message.edit_text(
            lang.msg_pay_link.format(link=link), reply_markup=get_to_main_localized(lang)
        )
    elif method == "CRYSTAL":
        link = await crystal_create_link(callback, amount, "RUB", days)
        await callback.message.edit_text(
            lang.msg_pay_link.format(link=link), reply_markup=get_to_main_localized(lang)
        )
    else:
        logging.warning("Unknown payment method from keyboard: %s", method)

    tariff_slug = await get_tariff_slug_by_days(method, days)
    await state.update_data(PaymentDays=days, PaymentMethod=method, TariffSlug=tariff_slug)
    await state.set_state(PaymentState.PaymentInvoice)

    if method in {"stars", "crypto", "SBP_APAY", "CRYSTAL"}:
        await notify_log(
            f"🧾 <b>Invoice created (bot)</b>\n"
            f"user: <code>{callback.from_user.id}</code> "
            f"@{esc(callback.from_user.username or '—')}\n"
            f"method: <code>{esc(PAYMENT_METHOD_NAMES.get(method, method))}</code>\n"
            f"amount: <code>{callback_data.amount}</code>\n"
            f"days: <code>{days}</code>\n"
            f"slug: <code>{esc(tariff_slug or '—')}</code>"
        )


@cp.invoice_paid()
async def payment_handler(invoice: Invoice, message: CallbackQuery):
    lang_user = await get_user_lang(message.from_user.id)
    await message.message.answer(lang_user.msg_order_paid.format(invoice_id=invoice.invoice_id))
    days = int(invoice.payload)
    transaction_id = str(uuid.uuid4())
    amount = getattr(invoice, "amount", 0)
    tariff_slug = await get_tariff_slug_by_days("crypto", days)
    await rq.create_transaction(
        user_tg_id=message.from_user.id,
        user_transaction=transaction_id,
        username=message.from_user.username,
        days=days,
        payment_method="CRYPTOPAY",
        amount=float(amount),
    )
    await rq.claim_order_for_processing(transaction_id)
    await deliver_subscription(
        message=message.message,
        username=message.from_user.username,
        user_id=message.from_user.id,
        days=days,
        subscription_type=SubscriptionType.PAID,
        payment_method=PAYMENT_METHOD_NAMES["crypto"],
        data_limit_gb=None,
        reset_strategy="no_reset",
        transaction_id=transaction_id,
        amount=float(amount),
        tariff_slug=tariff_slug,
    )


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def success_stars_payment_handler(message: Message, state: FSMContext):
    await state.set_state(PaymentState.PostPayment)
    states_data = await state.get_data()
    days = message.successful_payment.invoice_payload
    if not days or not days.isdigit():
        days = states_data.get("PaymentDays")
    if not days:
        logging.error("PaymentDays is None for user %s, cannot process payment", message.from_user.id)
        await message.answer("Ошибка: не удалось определить тариф. Обратитесь в поддержку.")
        await state.clear()
        await state.set_state(PaymentState.PrePayment)
        return

    transaction_id = str(uuid.uuid4())
    amount = message.successful_payment.total_amount
    await rq.create_transaction(
        user_tg_id=message.from_user.id,
        user_transaction=transaction_id,
        username=message.from_user.username,
        days=int(days),
        payment_method="TG_STARS",
        amount=float(amount),
    )
    await rq.claim_order_for_processing(transaction_id)

    tariff_slug = states_data.get("TariffSlug")
    await deliver_subscription(
        message=message,
        username=message.from_user.username,
        user_id=message.from_user.id,
        days=int(days),
        subscription_type=SubscriptionType.PAID,
        payment_method=PAYMENT_METHOD_NAMES["stars"],
        data_limit_gb=None,
        reset_strategy="no_reset",
        transaction_id=transaction_id,
        amount=float(amount),
        tariff_slug=tariff_slug,
    )

    await state.clear()
    await state.set_state(PaymentState.PrePayment)
