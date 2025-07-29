import os

from aiogram.types import InlineKeyboardButton, WebAppInfo, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def payment_keyboard(amount):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Оплатить {amount} ⭐️", pay=True)
    return builder.as_markup()


paystars_button = InlineKeyboardButton(
    text="🔒Telegram Stars⭐️",
    callback_data='Stars_Plans')

paystars_month = InlineKeyboardButton(
    text="🔒БЕЗЛИМИТ - 1 Месяц | 100⭐️",
    callback_data='Month_Plan')

premium_button = InlineKeyboardButton(
    text="🔒Приобрести CheezeVPN Premium⭐️",
    callback_data='Premium')

howto_button = InlineKeyboardButton(
    text="Как установить",
    callback_data='Others')

free_button = InlineKeyboardButton(
    text="Бесплатная версия",
    callback_data='Free')

android_button = InlineKeyboardButton(
    text="Android",
    web_app=WebAppInfo(url=os.environ["URL_PSNUS"])
)
ios_button = InlineKeyboardButton(
    text="IOS",
    web_app=WebAppInfo(url=os.environ["URL_NINT"])
)
win_button = InlineKeyboardButton(
    text="Windows",
    web_app=WebAppInfo(url=os.environ["URL_PSCARD"])
)
linux_button = InlineKeyboardButton(
    text="Linux",
    web_app=WebAppInfo(url=os.environ["URL_XBOX"])
)
to_main_button = InlineKeyboardButton(text='На главную', callback_data='Main')
# Собираем клавиатуру
main = InlineKeyboardMarkup(inline_keyboard=[[premium_button],
                                             [howto_button],
                                             [free_button]])

others = InlineKeyboardMarkup(inline_keyboard=[[android_button],
                                               [ios_button],
                                               [win_button],
                                               [linux_button],
                                               [to_main_button]])
pay_methods = InlineKeyboardMarkup(inline_keyboard=[[paystars_button]])
pay_tariffs = InlineKeyboardMarkup(inline_keyboard=[[paystars_month]])


def connect(link):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="v2RayTun", web_app=WebAppInfo(url=link))]])
