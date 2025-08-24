import logging
import app.keyboards as kb

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from app.settings import secrets

from app.settings import bot, cp
from app.handlers.tools import success_payment_handler
from app.locale.lang_ru import text_pay_method, text_extend_pay_method

from app.platega.platega import create_sbp_link

router = Router()


class PaymentState(StatesGroup):  # FSM States init
    PrePayment = State()
    PaymentMethod = State()
    PaymentTariff = State()
    PaymentInvoice = State()
    PostPayment = State()


@router.callback_query(F.data == 'Premium')
async def premium(callback: CallbackQuery, state: FSMContext):
    await callback.answer('Покупка Premium подписки')
    await callback.message.edit_text(text=text_pay_method, parse_mode="HTML",
                                     reply_markup=kb.pay_methods)
    await state.set_state(PaymentState.PaymentMethod)


@router.message(Command("test"), F.from_user.id == secrets.get('admin_id'))  # Testing ground
async def test_button(message: Message, state: FSMContext):
    await message.answer('Testing only')
    await message.answer(
        "Интеграция платежной системы",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="КУПИТЬ", callback_data="SBP_Plans")]
            ]
        )
    )
    await state.set_state(PaymentState.PaymentMethod)


@router.callback_query(F.data == 'Extend_Month')
async def premium(callback: CallbackQuery, state: FSMContext):
    await callback.answer('Продление Premium подписки')
    await callback.message.edit_text(text=text_extend_pay_method, parse_mode="HTML",
                                     reply_markup=kb.pay_methods)
    await state.set_state(PaymentState.PaymentMethod)


@router.callback_query(PaymentState.PaymentMethod)
async def stars_plan(callback: CallbackQuery, state: FSMContext):
    action = callback.data
    if action == 'Stars_Plans':
        await callback.message.edit_text('Выберите тарифный план', reply_markup=kb.starspay_tariffs)
        print("Stars has been chosen")
        await state.set_state(PaymentState.PaymentTariff)
    elif action == 'Crypto_Plans':
        await callback.message.edit_text('Выберите тарифный план', reply_markup=kb.cryptospay_tariffs)
        print("Crypto has been chosen")
        await state.set_state(PaymentState.PaymentTariff)
    elif action == 'SBP_Plans':
        await callback.message.edit_text('Выберите тарифный план', reply_markup=kb.sbp_tariffs)
        print("SBP has been chosen")
        await state.set_state(PaymentState.PaymentTariff)
    else:
        print("Wrong callback from methods keyboard")


@router.callback_query(kb.PaymentCallbackData.filter(F.tag == "data"), PaymentState.PaymentTariff)
async def invoice_handler(callback: CallbackQuery, callback_data: kb.PaymentCallbackData, state: FSMContext):
    method = callback_data.method
    amount = callback_data.amount
    days = callback_data.days
    if method == 'stars':
        await callback.answer('Оплата подписки в ⭐')
        prices = [LabeledPrice(label="XTR", amount=amount)]
        await bot.send_invoice(
            callback.from_user.id,
            title="Оплата подписки на месяц",
            description=f"Покупка за {amount} ⭐️!",
            prices=prices,
            provider_token="",
            payload="channel_support",
            currency="XTR",
            reply_markup=kb.payment_keyboard(int(amount)),
        )
        logging.info("Запускаю инвойс")
    elif method == 'crypto':
        invoice = await cp.create_invoice(amount, "USDT")
        await callback.message.edit_text(f"pay: {invoice.bot_invoice_url}")
        invoice.poll(message=callback.message)
        logging.info("Запускаю инвойс")
    elif method == 'SBP':
        link = await create_sbp_link(callback=callback, amount=amount, days=days)
        await callback.message.edit_text(f"Ссылка для оплаты: {link}")
    else:
        print('WRONG METHOD FROM KEYBOARD!')
    await state.update_data(PaymentDays=days)
    await state.set_state(PaymentState.PaymentInvoice)


@cp.invoice_polling()
async def handle_crypto_payment(invoice, message, state: FSMContext):
    await state.set_state(PaymentState.PostPayment)
    await message.answer(f"invoice #{invoice.invoice_id} has been paid")
    states_data = await state.get_data()
    days = states_data.get("PaymentDays")
    await success_payment_handler(message, tariff_days=int(days))
    await state.clear()
    await state.set_state(PaymentState.PrePayment)


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
    await success_payment_handler(message, tariff_days=int(days))
    await state.clear()
    await state.set_state(PaymentState.PrePayment)
