from aiogram.types import InlineKeyboardButton, WebAppInfo

paystars_button = InlineKeyboardButton(
    text="🔒Telegram Stars⭐️",
    callback_data='Stars_Plans')

paycryptobot_button = InlineKeyboardButton(
    text="🔒CryptoBot⭐️",
    callback_data='Crypto_Plans')

paysbp_button = InlineKeyboardButton(
    text="🔒СБП⭐️",
    callback_data='SBP_Plans')

apays_button = InlineKeyboardButton(
    text="🔒Банковская карта/перевод⭐️",
    callback_data='SBP_Apay')

crystal_button = InlineKeyboardButton(
    text="🔒Криптовалюта⭐️",
    callback_data='Crystal_plans')

to_pay_method_back = InlineKeyboardButton(
    text="Назад",
    callback_data='Premium')

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
    text="Android/IOS - Happ",
    callback_data='Android_Help')

windows_button = InlineKeyboardButton(
    text="Windows/Linux - Throne",
    callback_data='Windows_Help')

ios_button = InlineKeyboardButton(
    text="IOS"
)

win_button = InlineKeyboardButton(
    text="Windows"
)

linux_button = InlineKeyboardButton(
    text="Linux"
)

to_main_button = InlineKeyboardButton(text='На главную', callback_data='Main')

agreement_button = InlineKeyboardButton(
    text="Пользовательское соглашение",
    callback_data='Agreement')

privacy_button = InlineKeyboardButton(
    text="Политика конфиденциальности",
    callback_data='Privacy')

subcheck_button = InlineKeyboardButton(
    text="Я подписался!",
    callback_data='sub_check')

subcheck_free_button = InlineKeyboardButton(
    text="Я подписался!",
    callback_data='subcheck_free')


def to_web_info_button(link, text: str):
    return [InlineKeyboardButton(text=text,
                                 web_app=WebAppInfo(url=link)
                                 )]


def to_url_button(link, text: str):
    return [InlineKeyboardButton(text=text,
                                 url=link
                                 )]


cancel_broadcast_button = InlineKeyboardButton(text="Отменить рассылку",
                                               callback_data="cancel_broadcast")
