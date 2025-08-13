import time
import app.marzban.marzban as mz
import app.marzban.templates as templates
import app.keyboards as kb

from aiogram.types import Message, CallbackQuery

from app.handlers.events import main_menu


def time_to_unix(days: int):
    return int(days * 24 * 60 * 60)


async def get_user_days(user_nfo):
    return round((user_nfo["expire"] - time.time()) / (24 * 60 * 60))


async def get_user_info(message: Message):
    async with mz.MarzbanAsync() as marz:
        # await message.answer('Бесплатная версия (5 Гб в месяц)')
        user_info = await marz.get_user(name=message.from_user.username)
        return user_info


async def add_new_user_info(name, userid, limit, res_strat, expire_days: int):
    async with mz.MarzbanAsync() as marz:
        buyer_nfo = await marz.add_user(
            template=templates.vless_template,
            name=f"{name}",
            usrid=f"{userid}",
            limit=limit,
            res_strat=res_strat,  # no_reset day week month year
            expire=(int(time.time() + time_to_unix(expire_days)))
        )
    return buyer_nfo


async def set_user_info(name, limit, res_strat, expire_days: int):
    async with mz.MarzbanAsync() as marz:
        buyer_nfo = await marz.set_user(
            template=templates.vless_template,
            name=f"{name}",
            limit=limit,
            res_strat=res_strat,  # no_reset day week month year
            expire=(int(time.time() + time_to_unix(expire_days)))
        )
    return buyer_nfo


async def startup_user_dialog(message):
    user_info = await get_user_info(message)
    print(f"handler_type:{type(message).__name__}")
    if type(message).__name__ != "Message":
        message = message.message.edit_text
    else:
        message = message.answer
    if user_info == 404:
        print("User not found - starting main menu for newby")
        await main_menu(message, menu_type="new")
    else:
        print("User has been found - decide whats next")
        if user_info["status"] == "active" and user_info["data_limit"] is None:
            print("User has an active Pro subscription")
            await main_menu(message, menu_type="pro")
        else:
            if user_info["status"] == "active":
                print("User has an active Free subscription")
                await main_menu(message, menu_type="free")
            else:
                print("User has no active subscription")
                await main_menu(message, menu_type="new")


async def success_payment_handler(message: Message, tariff_days):
    await message.answer(text="🥳Оплата прошла успешно!🤗")
    user_info = await get_user_info(message)
    if user_info == 404:
        # print(user_info)
        print("Пользователь не найден - создание нового согласно тарифу")
        buyer_nfo = await add_new_user_info(message.from_user.username,
                                            message.from_user.id,
                                            limit=0,
                                            res_strat="no_reset",
                                            expire_days=tariff_days)
        expire_day = await get_user_days(buyer_nfo)
        sub_link = buyer_nfo["subscription_url"]
        await message.answer(text=f"❤️Cпасибо за покупку!\n\n"
                                  f"<b>Подписка оформлена</b>\n"
                                  f"Подписка будет действовать дней: {expire_day}\n"
                                  f"Ваша ссылка для подключения:\n"
                                  f"<code>{sub_link}</code>", parse_mode="HTML", reply_markup=kb.connect(sub_link))
    else:
        print("User found setting up new user info")
        sub_link = user_info["subscription_url"]
        status = user_info["status"]
        limit = user_info["data_limit"]
        if user_info["expire"] is None:
            expire_day = "Unlimited"
        else:
            expire_day = await get_user_days(user_info)
        if status == "active" and limit is None:
            buyer_nfo = await set_user_info(message.from_user.username,
                                            limit=0,
                                            res_strat='no_reset',
                                            expire_days=(expire_day + tariff_days))
            expire_day = expire_day + tariff_days
            await message.answer(text=f"❤️Cпасибо за покупку!\n\n"
                                      f"<b>Подписка успешно продлена еще на месяц</b>\n"
                                      f"Осталось дней: {expire_day}\n"
                                      f"Ваша ссылка для подключения:\n"
                                      f"<code>{sub_link}</code>", parse_mode="HTML",
                                 reply_markup=kb.connect(sub_link))

        else:
            buyer_nfo = await add_new_user_info(message.from_user.username,
                                                message.from_user.id,
                                                0,
                                                "no_reset",
                                                tariff_days)
            expire_day = await get_user_days(buyer_nfo)
            sub_link = buyer_nfo["subscription_url"]
            await message.answer(text=f"❤️Cпасибо за покупку!\n\n"
                                      f"<b>Подписка обновлена</b>\n"
                                      f"Осталось дней: {expire_day}\n"
                                      f"Ваша ссылка для подключения:\n"
                                      f"<code>{sub_link}</code>", parse_mode="HTML",
                                 reply_markup=kb.connect(sub_link))


async def free_sub_handler(callback, free_days, free_limit):
    user_info = await get_user_info(callback)
    # user_info = await get_user_info(message)
    if user_info == 404:
        print("User not found - making a new one")
        buyer_nfo = await add_new_user_info(callback.from_user.username,
                                            callback.from_user.id,
                                            free_limit * 1024 * 1024 * 1024,
                                            'month',
                                            free_days)
        print(buyer_nfo)
        expire_day = await get_user_days(buyer_nfo)
        sub_link = buyer_nfo["subscription_url"]
        await callback.message.answer(text=f"<b>Подписка оформлена</b>\n"
                                           f"Подписка будет действовать дней: {expire_day}\n"
                                           f"Ваша ссылка для подключения:\n"
                                           f"<code>{sub_link}</code>", parse_mode="HTML",
                                      reply_markup=kb.connect(sub_link))
    else:
        print("User found setting up new user info")
        sub_link = user_info["subscription_url"]
        # status = user_info["status"]
        # limit = user_info["data_limit"]
        if user_info["expire"] is None:
            expire_day = "Unlimited"
        else:
            expire_day = free_days
        buyer_nfo = await set_user_info(callback.from_user.username,
                                        free_limit * 1024 * 1024 * 1024,
                                        'month',
                                        free_days)
        await callback.message.answer(text=f"<b>Подписка успешно продлена еще на месяц</b>\n"
                                           f"Осталось дней: {expire_day}\n"
                                           f"Ваша ссылка для подключения:\n"
                                           f"<code>{sub_link}</code>", parse_mode="HTML",
                                      reply_markup=kb.connect(sub_link))


async def subscription_info(callback: CallbackQuery):
    user_info = await get_user_info(callback)
    print(callback.from_user.username)
    print(user_info)
    sub_link = user_info["subscription_url"]
    status = user_info["status"]
    limit = user_info["data_limit"]
    if user_info["expire"] is None:
        expire_day = "Unlimited"
    else:
        expire_day = await get_user_days(user_info)
    if status == "active" and limit is None:
        await callback.message.edit_text(f"Pro подписка активна\n"
                                         f"Осталось дней: {expire_day}\n", reply_markup=kb.connect(sub_link))
    else:
        await callback.message.edit_text("Free подписка активна\n"
                                         f"Осталось дней: {expire_day}\n", reply_markup=kb.connect(sub_link))

