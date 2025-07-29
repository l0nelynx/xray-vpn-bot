import logging
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.types import LabeledPrice, PreCheckoutQuery
from app.settings import bot
from app.handlers.events import start_bot, stop_bot, userlist
from app.utils import check_amount
from app.handlers.events import main_menu, main_call
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


@router.callback_query(F.data == 'Premium')
async def premium(callback: CallbackQuery):
    async with mz.MarzbanAsync() as marz:
            await callback.answer('Покупка Premium подписки')
            user_info = await marz.get_user(name=callback.from_user.username)
            if user_info == 404:
                print(user_info)
                await callback.message.answer('Текст описание+выберите способ оплаты', reply_markup=kb.pay_methods)
            else:
                print(user_info["username"])
                await callback.message.answer('Подписка уже активна+добавить функцию продления')


@router.callback_query(F.data == 'Free')
async def premium(callback: CallbackQuery):
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
                res_strat="month"  # no_reset day week month year
            )
            sub_link = buyer_nfo["subscription_url"]
            await callback.message.answer(text=f"🥳Ваши данные для подключения\n"
                                      f"ссылка:<code>{sub_link}</code>",parse_mode="HTML", reply_markup=kb.connect(sub_link))
        else:
            print(user_info["username"])
            sub_link = user_info["subscription_url"]
            await callback.message.answer('Подписка уже активна')
            await callback.message.answer(text=f"Ваши данные для подключения\n"
                                               f"ссылка:<code>{sub_link}</code>",parse_mode="HTML", reply_markup=kb.connect(sub_link))


@router.callback_query(F.data == 'Stars_Plans')
async def stars_plan(callback: CallbackQuery):
    await callback.answer('Выбор тарифного плана')
    await callback.message.answer('Выберите тарифный план', reply_markup=kb.pay_tariffs)


@router.callback_query(F.data == 'Month_Plan')
async def stars_month_plan(callback: CallbackQuery):
    await callback.answer('Оплата подписки на месяц')
    prices = [LabeledPrice(label="XTR", amount=1)]
    await bot.send_invoice(
        callback.from_user.id,
        title="Оплата подписки на месяц",
        description=f"Покупка за 1 ⭐️!",
        prices=prices,
        provider_token="",
        payload="channel_support",
        currency="XTR",
        reply_markup=payment_keyboard(check_amount(1)),
    )
    logging.info("Запускаю инвойс")


@router.message(Command("donate"))
async def send_invoice_handler(message: Message, command: CommandObject):
    prices = [LabeledPrice(label="XTR", amount=check_amount(command.args))]
    await message.answer_invoice(
        title="Поддержка канала",
        description=f"Поддержать сервис на {check_amount(command.args)} ⭐️!",
        prices=prices,
        provider_token="",
        payload="channel_support",
        currency="XTR",
        reply_markup=payment_keyboard(check_amount(command.args)),
    )
    logging.info("Запускаю инвойс")


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    logging.info("Запускаю pre_checkout_handler")
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def success_payment_handler(message: Message):
    await message.answer(text="🥳Оплата прошла успешно!🤗")
    async with mz.MarzbanAsync() as marz:
        buyer_nfo = await marz.add_user(
            template=mz.vless_template,
            name=f"{message.from_user.username}",
            usrid=f"{message.from_user.id}",
            limit=0,
            res_strat="month"  # no_reset day week month year
        )
        sub_link = buyer_nfo["subscription_url"]
        await message.answer(text=f"🥳Ваши данные для подключения\n"
                            f"ссылка:<code>{sub_link}</code>",parse_mode="HTML")
