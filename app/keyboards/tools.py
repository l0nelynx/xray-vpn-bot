from typing import Callable, Dict

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.settings import secrets

price_stars = secrets.get('stars_price')
price_crypto = secrets.get('crypto_price')
price_discount = secrets.get('discount')
sbp_price = secrets.get('sbp_price')


class PaymentCallbackData(CallbackData, prefix=""):
    tag: str
    method: str
    amount: float
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
    def default_discount(amount: float, discount_percent: int) -> float:
        """Стандартная функция расчета скидки"""
        print(amount * (1 - discount_percent / 100))
        return amount * (1 - discount_percent / 100)

    def calculate_amount(self) -> float:
        """Рассчет итоговой суммы с учетом скидки"""
        monthly_cost = self.price * (self.days / 30)
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
        base_price,
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
