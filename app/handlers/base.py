import logging
import time
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.types import LabeledPrice, PreCheckoutQuery
from app.settings import bot, cp
from app.handlers.events import start_bot, stop_bot, userlist
from app.handlers.tools import success_payment_handler
from app.utils import check_amount
from app.handlers.events import main_menu, main_call
from app.locale.lang_ru import text_help
import app.database.requests as rq
import app.marzban.marzban as mz
from app.keyboards import payment_keyboard
import app.keyboards as kb
from app.settings import Secrets

router = Router()
# vpn = mz.MarzbanAsync()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await rq.set_user(message.from_user.id)
    await main_menu(message)
    # Отправляем сообщение с кнопкой


@router.message(Command("users"), F.from_user.id == Secrets.admin_id)
async def user_db_check(message: Message):
    await userlist()


@router.callback_query(F.data == 'Main')
async def others(callback: CallbackQuery):
    await callback.answer('Вы в главном меню')
    await main_call(callback)


@router.callback_query(F.data == 'Others')
async def others(callback: CallbackQuery):
    await callback.answer('Раздел инструкций')
    await callback.message.answer('Выберите свою платформу:', reply_markup=kb.others)


@router.callback_query(F.data == 'Android_Help')
async def others(callback: CallbackQuery):
    await callback.answer('Инструкция для Android')
    await callback.message.answer(text=text_help, parse_mode='HTML', disable_web_page_preview=True, reply_markup=kb.others)


@router.callback_query(F.data == 'Premium')
async def premium(callback: CallbackQuery):
    async with mz.MarzbanAsync() as marz:
            await callback.answer('Покупка Premium подписки')
            user_info = await marz.get_user(name=callback.from_user.username)
            if user_info == 404:
                print(user_info)
                await callback.message.answer('Выберите способ оплаты для покупки Premium подписки:', reply_markup=kb.pay_methods)
            else:
                limit = user_info["data_limit"]
                print(limit)
                status = user_info["status"]
                if status == "active":
                    if limit is None:
                        await callback.message.answer('Premium подписка уже активна, но вы можете ее продлить\n'
                                                      'Выберите способ оплаты для продления подписки:', reply_markup=kb.pay_methods)
                    else:
                        await callback.message.answer('У вас активна бесплатная подписка\n'
                                                        'Но вы можете ее проапгрейдить до Premium\n', reply_markup=kb.pay_methods)
                else:
                    await callback.message.answer('Выберите способ оплаты для покупки Premium подписки:', reply_markup=kb.pay_methods)


@router.callback_query(F.data == 'Free')
async def free_buy(callback: CallbackQuery):
    async with mz.MarzbanAsync() as marz:
        await callback.answer('Бесплатная версия (5 Гб в месяц)')
        user_info = await marz.get_user(name=callback.from_user.username)
        if user_info == 404:
            print(user_info)
            buyer_nfo = await marz.add_user(
                template=mz.vless_template,
                name=f"{callback.from_user.username}",
                usrid=f"{callback.from_user.id}",
                limit=5*1024*1024*1024,
                res_strat="month",  # no_reset day week month year
                expire=(int(time.time()+30*24*60*60))
            )
            if buyer_nfo["expire"] is None:
                expire_day = "Unlimited"
            else:
                expire_day = round((buyer_nfo["expire"] - time.time()) / (24 * 60 * 60))
            sub_link = buyer_nfo["subscription_url"]
            await callback.message.answer(text=f"<b>Подписка оформлена</b>\n"
                                               f"Подписка будет действовать дней: {expire_day}\n"
                                               f"Ваша ссылка для подключения:\n"
                                               f"<code>{sub_link}</code>",parse_mode="HTML", reply_markup=kb.connect(sub_link))
        else:
            print(user_info["username"])
            sub_link = user_info["subscription_url"]
            status = user_info["status"]
            if user_info["expire"] is None:
                expire_day = "Unlimited"
            else:
                expire_day = round((user_info["expire"] - time.time()) / (24 * 60 * 60))
            if status == "active":
                await callback.message.answer(text=f"<b>Подписка уже активна</b>\n"
                                                   f"Осталось дней: {expire_day}\n"
                                                   f"Ваша ссылка для подключения:\n"
                                                   f"<code>{sub_link}</code>",parse_mode="HTML", reply_markup=kb.connect(sub_link))
            else:
                buyer_nfo = await marz.set_user(
                template=mz.vless_template,
                name=f"{callback.from_user.username}",
                limit=5*1024*1024*1024,
                res_strat="month",  # no_reset day week month year
                expire=(int(time.time()+30*24*60*60))
                )
                await callback.message.answer(text=f"<b>Подписка продлена</b>\n"
                                                   f"Осталось дней: {expire_day}\n"
                                                   f"Ваша ссылка для подключения:\n"
                                                   f"<code>{sub_link}</code>",parse_mode="HTML", reply_markup=kb.connect(sub_link))


@router.callback_query(F.data == 'Stars_Plans')
async def stars_plan(callback: CallbackQuery):
    await callback.answer('Выбор тарифного плана')
    await callback.message.answer('Выберите тарифный план', reply_markup=kb.starspay_tariffs)


@router.callback_query(F.data == 'Crypto_Plans')
async def stars_plan(callback: CallbackQuery):
    await callback.answer('Выбор тарифного плана')
    await callback.message.answer('Выберите тарифный план', reply_markup=kb.cryptospay_tariffs)


@router.callback_query(F.data == 'Crypto_Month_Plan')
async def cryptobot_month_plan(callback: CallbackQuery):
    invoice = await cp.create_invoice(2, "USDT")
    await callback.message.answer(f"pay: {invoice.bot_invoice_url}")
    invoice.poll(message=callback.message)
    logging.info("Запускаю инвойс")


@cp.invoice_polling()
async def handle_crypto_payment(invoice, message):
    await message.answer(f"invoice #{invoice.invoice_id} has been paid")
    await success_payment_handler(message)


@router.callback_query(F.data == 'Month_Plan')
async def stars_month_plan(callback: CallbackQuery):
    await callback.answer('Оплата подписки на месяц')
    prices = [LabeledPrice(label="XTR", amount=150)]
    await bot.send_invoice(
        callback.from_user.id,
        title="Оплата подписки на месяц",
        description=f"Покупка за 150 ⭐️!",
        prices=prices,
        provider_token="",
        payload="channel_support",
        currency="XTR",
        reply_markup=payment_keyboard(check_amount(150)),
    )
    logging.info("Запускаю инвойс")


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    logging.info("Запускаю pre_checkout_handler")
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def success_stars_payment_handler(message: Message):
    await success_payment_handler(message)