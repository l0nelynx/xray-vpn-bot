import os

from aiogram.types import InlineKeyboardButton, WebAppInfo, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from app.settings import Secrets

price_stars = Secrets.stars_price
price_crypto = Secrets.crypto_price


class PaymentCallbackData(CallbackData, prefix=""):
    tag: str
    method: str
    amount: int
    days: int


def payment_keyboard(amount):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Оплатить {amount} ⭐️", pay=True)
    return builder.as_markup()


paystars_button = InlineKeyboardButton(
    text="🔒Telegram Stars⭐️",
    callback_data='Stars_Plans')

paycryptobot_button = InlineKeyboardButton(
    text="🔒Crypto⭐️",
    callback_data='Crypto_Plans')

to_pay_method_back = InlineKeyboardButton(
    text="Назад",
    callback_data='Premium')

paystars_month = InlineKeyboardButton(
    text=f"🔒БЕЗЛИМИТ - 1 Месяц | {price_stars}⭐️",
    callback_data=PaymentCallbackData(tag='data', method='stars', amount=price_stars, days=30).pack())

paycryptobot_month = InlineKeyboardButton(
    text=f"🔒БЕЗЛИМИТ - 1 Месяц | {price_crypto} USDT",
    callback_data=PaymentCallbackData(tag='data', method='crypto', amount=price_crypto, days=30).pack())

premium_button = InlineKeyboardButton(
    text="🔒Приобрести CheezeVPN Premium⭐️",
    callback_data='Premium')

extend_button = InlineKeyboardButton(
    text="🔒Продлить подписку ️",
    callback_data='Extend_Month')

status_button = InlineKeyboardButton(
    text="Информация о подписке",
    callback_data='Sub_Info')

howto_button = InlineKeyboardButton(
    text="Инструкция по установке",
    callback_data='Others')

free_button = InlineKeyboardButton(
    text="Бесплатная версия",
    callback_data='Free')

android_button = InlineKeyboardButton(
    text="Android/IOS",
    callback_data='Android_Help')

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
main_new = InlineKeyboardMarkup(inline_keyboard=[[premium_button],
                                                 [howto_button],
                                                 [free_button]])
main_pro = InlineKeyboardMarkup(inline_keyboard=[[extend_button],
                                                 [howto_button],
                                                 [status_button]])
main_free = InlineKeyboardMarkup(inline_keyboard=[[premium_button],
                                                  [howto_button],
                                                  [status_button]])

others = InlineKeyboardMarkup(inline_keyboard=[[android_button],
                                               # [ios_button],
                                               # [win_button],
                                               # [linux_button],
                                               [to_main_button]])
pay_methods = InlineKeyboardMarkup(inline_keyboard=[[paystars_button],
                                                    [paycryptobot_button],
                                                    [to_main_button]])
starspay_tariffs = InlineKeyboardMarkup(inline_keyboard=[[paystars_month],
                                                         [to_pay_method_back],
                                                         [to_main_button]])
cryptospay_tariffs = InlineKeyboardMarkup(inline_keyboard=[[paycryptobot_month],
                                                           [to_pay_method_back],
                                                           [to_main_button]])
pay_extend_month = InlineKeyboardMarkup(inline_keyboard=[[extend_button],
                                                         [to_main_button]])


def connect(link):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Подробнее", web_app=WebAppInfo(url=link))],
                                                 [to_main_button]])
