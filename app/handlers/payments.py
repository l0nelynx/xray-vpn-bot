import logging
import uuid

from aiogram import F, Router

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.types import Message, CallbackQuery

from aiosend.types import Invoice

import app.keyboards as kb
from app.api.a_pay import create_sbp_link as apays_create_sbp_link
from app.api.crystal_pay import crystal_create_link
from app.handlers.tools import success_payment_handler
from app.handlers.subscription_service import deliver_subscription, SubscriptionType
from app.locale.utils import get_user_lang
from app.keyboards.localized import get_pay_methods_localized, get_to_main_localized
from app.keyboards.tools import create_tariff_keyboard, get_price_stars, get_price_crypto, get_sbp_price
from app.tariffs import get_tariffs_stars, get_tariffs_crypto, get_tariffs_sbp
from app.settings import bot, cp, secrets
import app.database.requests as rq


router = Router()

# Маппинг методов оплаты на названия для логирования
PAYMENT_METHOD_NAMES = {
    'stars': 'TG_STARS',
    'crypto': 'CRYPTOPAY',
    'SBP_APAY': 'SBP_APAY',
    'CRYSTAL': 'CRYSTAL_PAY'
}


class PaymentState(StatesGroup):  # FSM States init
    PrePayment = State()
    PaymentMethod = State()
    PaymentTariff = State()
    PaymentInvoice = State()
    PostPayment = State()
    PromoInput = State()


@router.callback_query(F.data == 'Premium')
async def premium(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer(lang.msg_buying_premium)
    show_promo = await rq.can_use_promo(callback.from_user.id)
    await callback.message.edit_text(text=lang.text_pay_method, parse_mode="HTML",
                                     reply_markup=get_pay_methods_localized(lang, show_promo=show_promo))
    await state.set_state(PaymentState.PaymentMethod)


@router.callback_query(F.data == 'Extend_Month')
async def premium_extend(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer(lang.msg_extending_premium)
    show_promo = await rq.can_use_promo(callback.from_user.id)
    await callback.message.edit_text(text=lang.text_extend_pay_method, parse_mode="HTML",
                                     reply_markup=get_pay_methods_localized(lang, show_promo=show_promo))
    await state.set_state(PaymentState.PaymentMethod)


@router.callback_query(F.data == 'Enter_Promo', PaymentState.PaymentMethod)
async def enter_promo(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(text=lang.promo_enter_text, parse_mode='HTML')
    await state.set_state(PaymentState.PromoInput)


@router.message(PaymentState.PromoInput)
async def process_promo_input(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)

    promo_code = message.text.strip().upper()
    tg_id = message.from_user.id

    # Check if user can still use a promo
    can_use = await rq.can_use_promo(tg_id)
    if not can_use:
        await message.answer(text=lang.promo_already_used_text, parse_mode='HTML',
                             reply_markup=get_pay_methods_localized(lang, show_promo=False))
        await state.set_state(PaymentState.PaymentMethod)
        return

    # Check if promo exists
    promo = await rq.get_promo_by_code(promo_code)
    if not promo:
        await message.answer(text=lang.promo_invalid_text, parse_mode='HTML',
                             reply_markup=get_pay_methods_localized(lang, show_promo=True))
        await state.set_state(PaymentState.PaymentMethod)
        return

    # Check if user tries to use their own promo
    if promo['tg_id'] == tg_id:
        await message.answer(text=lang.promo_own_code_text, parse_mode='HTML',
                             reply_markup=get_pay_methods_localized(lang, show_promo=True))
        await state.set_state(PaymentState.PaymentMethod)
        return

    # Apply promo
    promo_discount = secrets.get('promo_discount', 20)
    await rq.use_promo(tg_id, promo_code)
    await state.update_data(PromoDiscount=promo_discount, PromoCode=promo_code)

    await message.answer(
        text=lang.promo_success_text.format(discount=promo_discount),
        parse_mode='HTML',
        reply_markup=get_pay_methods_localized(lang, show_promo=False)
    )
    await state.set_state(PaymentState.PaymentMethod)


@router.callback_query(PaymentState.PaymentMethod)
async def stars_plan(callback: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    promo_discount = state_data.get('PromoDiscount', 0)

    # Build tariff keyboards dynamically with promo discount
    keyboards = {
        'Stars_Plans': lambda: create_tariff_keyboard(tariff=get_tariffs_stars(), method='stars', base_price=get_price_stars(), extra_discount=promo_discount),
        'Crypto_Plans': lambda: create_tariff_keyboard(tariff=get_tariffs_crypto(), method='crypto', base_price=get_price_crypto(), extra_discount=promo_discount),
        'SBP_Plans': lambda: create_tariff_keyboard(tariff=get_tariffs_sbp(), method='SBP', base_price=get_sbp_price(), extra_discount=promo_discount),
        'SBP_Apay': lambda: create_tariff_keyboard(tariff=get_tariffs_sbp(), method='SBP_APAY', base_price=get_sbp_price(), extra_discount=promo_discount),
        'Crystal_plans': lambda: create_tariff_keyboard(tariff=get_tariffs_sbp(), method='CRYSTAL', base_price=get_sbp_price(), extra_discount=promo_discount),
    }

    builder = keyboards.get(callback.data)
    if builder:
        keyboard = builder()
        lang = await get_user_lang(callback.from_user.id)
        await callback.message.edit_text(lang.msg_choose_tariff, reply_markup=keyboard)
        print(f"{callback.data.split('_')[0]} has been chosen")
        await state.set_state(PaymentState.PaymentTariff)
    else:
        print("Wrong callback from methods keyboard")


@router.callback_query(kb.PaymentCallbackData.filter(F.tag == "data"), PaymentState.PaymentTariff)
async def invoice_handler(callback: CallbackQuery, callback_data: kb.PaymentCallbackData, state: FSMContext):
    method = callback_data.method
    amount = callback_data.amount
    days = callback_data.days
    lang = await get_user_lang(callback.from_user.id)
    if method == 'stars':
        await callback.answer(lang.msg_pay_in_stars)
        prices = [LabeledPrice(label="XTR", amount=int(round(amount)))]
        await bot.send_invoice(
            callback.from_user.id,
            title=lang.msg_invoice_title,
            description=lang.msg_invoice_description.format(amount=int(round(amount))),
            prices=prices,
            provider_token="",
            payload="channel_support",
            currency="XTR",
            reply_markup=kb.payment_keyboard(int(round(amount))),
        )
        logging.info("Запускаю инвойс для TG Stars")
    elif method == 'crypto':
        invoice = await cp.create_invoice(amount, "USDT", payload = f"{days}")
        await callback.message.edit_text(f"pay: {invoice.bot_invoice_url}")
        invoice.poll(message=callback)
        logging.info("Запускаю инвойс для Crypto")
        await state.clear()
        await state.set_state(PaymentState.PrePayment)
    elif method == 'SBP_APAY':
        amount = int(round(amount * 100))
        link = await apays_create_sbp_link(callback=callback, amount=amount, days=days)
        await callback.message.edit_text(lang.msg_pay_link.format(link=link), reply_markup=get_to_main_localized(lang))
        logging.info("Запускаю ссылку оплаты для SBP APAY")
    elif method == 'CRYSTAL':
        link = await crystal_create_link(callback, amount, 'RUB', days)
        await callback.message.edit_text(lang.msg_pay_link.format(link=link), reply_markup=get_to_main_localized(lang))
        logging.info("Запускаю ссылку оплаты для Crystal Pay")
    else:
        print('WRONG METHOD FROM KEYBOARD!')

    await state.update_data(PaymentDays=days, PaymentMethod=method)
    await state.set_state(PaymentState.PaymentInvoice)


@cp.invoice_paid()
async def payment_handler(invoice: Invoice, message: CallbackQuery):
    lang_user = await get_user_lang(message.from_user.id)
    await message.message.answer(lang_user.msg_order_paid.format(invoice_id=invoice.invoice_id))
    days = int(invoice.payload)
    transaction_id = str(uuid.uuid4())
    amount = getattr(invoice, 'amount', 0)
    await rq.create_transaction(
        user_tg_id=message.from_user.id,
        user_transaction=transaction_id,
        username=message.from_user.username,
        days=days,
        payment_method='CRYPTOPAY',
        amount=float(amount),
    )
    await rq.claim_order_for_processing(transaction_id)
    await deliver_subscription(
        message=message.message,
        username=message.from_user.username,
        user_id=message.from_user.id,
        days=days,
        subscription_type=SubscriptionType.PAID,
        payment_method=PAYMENT_METHOD_NAMES['crypto'],
        data_limit_gb=None,
        reset_strategy="no_reset",
        transaction_id=transaction_id,
        amount=float(amount),
    )


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    logging.info("Запускаю pre_checkout_handler")
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def success_stars_payment_handler(message: Message, state: FSMContext):
    await state.set_state(PaymentState.PostPayment)
    states_data = await state.get_data()
    print(states_data)
    days = states_data.get("PaymentDays")
    transaction_id = str(uuid.uuid4())
    amount = message.successful_payment.total_amount
    await rq.create_transaction(
        user_tg_id=message.from_user.id,
        user_transaction=transaction_id,
        username=message.from_user.username,
        days=int(days),
        payment_method='TG_STARS',
        amount=float(amount),
    )
    await rq.claim_order_for_processing(transaction_id)

    await deliver_subscription(
        message=message,
        username=message.from_user.username,
        user_id=message.from_user.id,
        days=int(days),
        subscription_type=SubscriptionType.PAID,
        payment_method=PAYMENT_METHOD_NAMES['stars'],
        data_limit_gb=None,
        reset_strategy="no_reset",
        transaction_id=transaction_id,
        amount=float(amount),
    )

    await state.clear()
    await state.set_state(PaymentState.PrePayment)
