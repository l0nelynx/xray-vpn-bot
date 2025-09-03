from aiogram.types import InlineKeyboardButton, WebAppInfo, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

from typing import Callable, Dict

from app.settings import secrets
from app.tariffs import tariffs_stars, tariffs_crypto, tariffs_sbp

# from app.utils import discount

price_stars = secrets.get('stars_price')
price_crypto = secrets.get('crypto_price')
price_discount = secrets.get('discount')
sbp_price = secrets.get('sbp_price')


class PaymentCallbackData(CallbackData, prefix=""):
    tag: str
    method: str
    amount: int
    days: int


def payment_keyboard(amount):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Оплатить {amount} ⭐️", pay=True)
    return builder.as_markup()


class TariffKeyboardBuilder:
    def __init__(
            self,
            method: str,
            price: int,
            days: int,
            disc: int,
            currency: str,
            period: str,
            discount_func: Callable[[float, int], float] = None
    ):
        """
        Конструктор класса для создания кнопки тарифа

        :param method: Способ оплаты
        :param price: Цена за месяц
        :param days: Количество дней в тарифе
        :param disc: Процент скидки
        :param currency: Валюта (символ)
        :param period: Описание периода
        :param discount_func: Функция расчета скидки (по умолчанинию стандартная)
        """
        self.method = method
        self.price = price
        self.days = days
        self.disc = disc
        self.currency = currency
        self.period = period
        self.discount_func = discount_func or self.default_discount

    @staticmethod
    def default_discount(amount: int, discount_percent: int) -> int:
        """Стандартная функция расчета скидки"""
        return round(amount * (1 - discount_percent / 100))

    def calculate_amount(self) -> int:
        """Рассчет итоговой суммы с учетом скидки"""
        monthly_cost = round(self.price * (self.days / 30))
        print(monthly_cost)
        return self.discount_func(monthly_cost, self.disc)

    def build(self) -> InlineKeyboardButton:
        """Создание кнопки с тарифом"""
        amount = self.calculate_amount()

        call_data = PaymentCallbackData(
            tag='data',
            method=self.method,
            amount=amount,
            days=self.days
        ).pack()

        # Форматирование текста: добавление валюты и форматирование цены
        formatted_price = f"{amount:.2f}".rstrip('0').rstrip('.')
        text = f"🔒БЕЗЛИМИТ - {self.period} | {formatted_price} {self.currency}"

        return InlineKeyboardButton(text=text, callback_data=call_data)


def create_tariff_keyboard(
        tariff: Dict[str, dict],
        method: str,
        base_price: int,
        discount_func: Callable[[float, int], float] = None
) -> InlineKeyboardMarkup:
    # Формируем список строк (каждая строка - список из одной кнопки)
    keyboard = []

    for name, params in tariff.items():
        days = int(params['days'])
        disc = int(params['disc'])
        currency = params['currency']
        period = params['period']

        builder = TariffKeyboardBuilder(
            method=method,
            price=base_price,
            days=days,
            disc=disc,
            currency=currency,
            period=period,
            discount_func=discount_func
        )

        # Каждая кнопка в отдельном списке = отдельная строка
        keyboard.append([builder.build()])
    keyboard.append([InlineKeyboardButton(text="Назад", callback_data='Premium')])
    keyboard.append([InlineKeyboardButton(text='На главную', callback_data='Main')])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


paystars_button = InlineKeyboardButton(
    text="🔒Telegram Stars⭐️",
    callback_data='Stars_Plans')

paycryptobot_button = InlineKeyboardButton(
    text="🔒Crypto⭐️",
    callback_data='Crypto_Plans')

paysbp_button = InlineKeyboardButton(
    text="🔒СБП⭐️",
    callback_data='SBP_Plans')

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
    text="Android/IOS",
    callback_data='Android_Help')

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

# Собираем клавиатуру
main_new = InlineKeyboardMarkup(inline_keyboard=[[premium_button],
                                                 [howto_button],
                                                 [free_button],
                                                 [agreement_button],
                                                 [privacy_button]])
main_pro = InlineKeyboardMarkup(inline_keyboard=[[extend_button],
                                                 [howto_button],
                                                 [status_button],
                                                 [agreement_button],
                                                 [privacy_button]])
main_free = InlineKeyboardMarkup(inline_keyboard=[[premium_button],
                                                  [howto_button],
                                                  [status_button],
                                                  [agreement_button],
                                                  [privacy_button]])

others = InlineKeyboardMarkup(inline_keyboard=[[android_button],
                                               # [ios_button],
                                               # [win_button],
                                               # [linux_button],
                                               [to_main_button]])
pay_methods = InlineKeyboardMarkup(inline_keyboard=[[paystars_button],
                                                    [paycryptobot_button],
                                                    # [paysbp_button],
                                                    [to_main_button]])

starspay_tariffs = create_tariff_keyboard(tariff=tariffs_stars, method='stars', base_price=price_stars)
cryptospay_tariffs = create_tariff_keyboard(tariff=tariffs_crypto, method='crypto', base_price=price_crypto)
sbp_tariffs = create_tariff_keyboard(tariff=tariffs_sbp, method='SBP', base_price=sbp_price)
sbp_apay_tariffs = create_tariff_keyboard(tariff=tariffs_sbp, method='SBP_APAY', base_price=sbp_price)
pay_extend_month = InlineKeyboardMarkup(inline_keyboard=[[extend_button],
                                                         [to_main_button]])
to_main = InlineKeyboardMarkup(inline_keyboard=[[to_main_button]])
agreement_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Полный текст",
                          web_app=WebAppInfo(url=secrets.get('agreement_url'))
                          )], [to_main_button]])
policy_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Полный текст",
                          web_app=WebAppInfo(url=secrets.get('policy_url'))
                          )], [to_main_button]])


def connect(link):
    # if link:
    #   v2raytun_url = f"v2raytun://import/{link[8:]}"
    #   redirect_url = f"{secrets.get('marz_url')}/go?url={v2raytun_url}"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Подробнее",
                                                                       # url=redirect_url,
                                                                       web_app=WebAppInfo(url=link)
                                                                       )],
                                                 [to_main_button]])
