import logging
import time
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from app.settings import bot, cp
from app.handlers.events import start_bot, stop_bot, userlist
from app.handlers.tools import success_payment_handler
from app.utils import check_amount
from app.handlers.events import main_menu, main_call
from app.locale.lang_ru import text_help, text_pay_method, text_extend_pay_method
from app.handlers.tools import get_user_info, set_user_info, startup_user_dialog, free_sub_handler, subscription_info
import app.database.requests as rq
import app.marzban.marzban as mz
from app.keyboards import payment_keyboard, PaymentCallbackData
import app.keyboards as kb
from app.settings import Secrets
from aiogram.fsm.state import State, StatesGroup

router = Router()


# vpn = mz.MarzbanAsync()
class PaymentState (StatesGroup):
    PrePayment = State()
    PaymentMethod = State()
    PaymentTariff = State()
    PaymentInvoice = State()
    PostPayment = State()

    #@dp.callback_query(call: call.data == "check", PaymentState.PrePayment) # Хендлер работающий в определенном состоянии
    #async def check_transaction(call: CallbackQuery, state: FSMContext): #FSMСontext

    # await state.set_state(PaymentState.PrePayment) # Задать состояние
    # await state.update_data(PaymentAmount=amount) # Задать данные в состояние
    # await state.set_state(PaymentState.Payment) # Задать состояние
    # payment_data = await state.get_data() # Получить все данные состояния
    # amount = user_data['PaymentAmount'] #Получить конкретные данные
    # await state.set_state(PaymentState.PostPayment) # Задать состояние
    # await state.clear() # Очистить данные в конце
    # await state.set_state(PaymentState.PrePayment) # Сбросить состояние в начало


@router.message(Command("start"))
async def cmd_start(message: Message):
    await rq.set_user(message.from_user.id)
    await startup_user_dialog(message)


@router.message(Command("users"), F.from_user.id == Secrets.admin_id)
async def user_db_check(message: Message):
    await userlist()


@router.callback_query(F.data == 'Main')
async def others(callback: CallbackQuery):
    await callback.answer('Вы в главном меню')
    await startup_user_dialog(callback)


@router.callback_query(F.data == 'Others')
async def others(callback: CallbackQuery):
    await callback.answer('Раздел инструкций')
    await callback.message.edit_text('Выберите свою платформу:', reply_markup=kb.others)


@router.callback_query(F.data == 'Android_Help')
async def others(callback: CallbackQuery):
    await callback.answer('Инструкция для Android')
    await callback.message.edit_text(text=text_help, parse_mode='HTML', disable_web_page_preview=True,
                                  reply_markup=kb.others)


@router.callback_query(F.data == 'Premium')
async def premium(callback: CallbackQuery, state: FSMContext):
    await callback.answer('Покупка Premium подписки')
    await callback.message.edit_text(text=text_pay_method, parse_mode="HTML",
                                  reply_markup=kb.pay_methods)
    await state.set_state(PaymentState.PaymentMethod)


@router.callback_query(F.data == 'Extend_Month')
async def premium(callback: CallbackQuery, state: FSMContext):
    await callback.answer('Продление Premium подписки')
    await callback.message.edit_text(text=text_extend_pay_method, parse_mode="HTML",
                                     reply_markup=kb.pay_methods)
    await state.set_state(PaymentState.PaymentMethod)


@router.callback_query(F.data == 'Free')
async def free_buy(callback: CallbackQuery):
    await free_sub_handler(callback, 30, 5)


@router.callback_query(F.data == 'Sub_Info')
async def get_subscription_info(callback: CallbackQuery):
    await subscription_info(callback)


@router.callback_query(PaymentState.PaymentMethod)
async def stars_plan(callback: CallbackQuery, state: FSMContext):
    action = callback.data
    if action == 'Stars_Plans':
        await callback.message.edit_text('Выберите тарифный план', reply_markup=kb.starspay_tariffs)
        print("Stars has been chosen")
        await state.set_state(PaymentState.PaymentTariff)
        #await state.update_data(PaymentMethod='Stars')
    else:
        await callback.message.edit_text('Выберите тарифный план', reply_markup=kb.cryptospay_tariffs)
        print("Crypto has been chosen")
        await state.set_state(PaymentState.PaymentTariff)
        #await state.update_data(PaymentMethod='Crypto')


# @router.callback_query(F.data == 'Stars_Plans')
# async def stars_plan(callback: CallbackQuery):
#     await callback.answer('Выбор тарифного плана')
#     await callback.message.edit_text('Выберите тарифный план', reply_markup=kb.cryptospay_tariffs)
#
#
# @router.callback_query(F.data == 'Crypto_Plans')
# async def stars_plan(callback: CallbackQuery):
#     await callback.answer('Выбор тарифного плана')
#     await callback.message.edit_text('Выберите тарифный план', reply_markup=kb.cryptospay_tariffs)


@router.callback_query(PaymentCallbackData.filter(F.tag == "data"), PaymentState.PaymentTariff)
async def invoice_handler(callback: CallbackQuery, callback_data: PaymentCallbackData, state: FSMContext):
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
            reply_markup=payment_keyboard(check_amount(int(amount))),
        )
        logging.info("Запускаю инвойс")
    else:
        invoice = await cp.create_invoice(amount, "USDT")
        await callback.message.edit_text(f"pay: {invoice.bot_invoice_url}")
        invoice.poll(message=callback.message)
        logging.info("Запускаю инвойс")
    await state.update_data(PaymentDays=days)
    await state.set_state(PaymentState.PaymentInvoice)


# @router.callback_query(F.data == 'Crypto_Month_Plan')
# async def cryptobot_month_plan(callback: CallbackQuery):
#     invoice = await cp.create_invoice(2, "USDT")
#     await callback.message.answer(f"pay: {invoice.bot_invoice_url}")
#     invoice.poll(message=callback.message)
#     logging.info("Запускаю инвойс")


@cp.invoice_polling()
async def handle_crypto_payment(invoice, message, state: FSMContext):
    await state.set_state(PaymentState.PostPayment)
    await message.answer(f"invoice #{invoice.invoice_id} has been paid")
    states_data = await state.get_data()
    days = states_data.get("PaymentDays")
    await success_payment_handler(message, tariff_days=int(days))
    await state.clear()
    await state.set_state(PaymentState.PrePayment)


#@router.callback_query(F.data == 'Month_Plan')
# async def stars_month_plan(callback: CallbackQuery):
#     await callback.answer('Оплата подписки на месяц')
#     prices = [LabeledPrice(label="XTR", amount=150)]
#     await bot.send_invoice(
#         callback.from_user.id,
#         title="Оплата подписки на месяц",
#         description=f"Покупка за 150 ⭐️!",
#         prices=prices,
#         provider_token="",
#         payload="channel_support",
#         currency="XTR",
#         reply_markup=payment_keyboard(check_amount(150)),
#     )
#     logging.info("Запускаю инвойс")


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
