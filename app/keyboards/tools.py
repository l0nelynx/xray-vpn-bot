"""
Optimized keyboard tools module for aiogram.
Implements efficient tariff keyboard building with caching and performance improvements.
"""
from typing import Callable, Dict, Optional

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.settings import secrets


def get_price_stars():
    return secrets.get('stars_price')


def get_price_crypto():
    return secrets.get('crypto_price')


def get_price_discount():
    return secrets.get('discount')


def get_sbp_price():
    return secrets.get('sbp_price')


class PaymentCallbackData(CallbackData, prefix=""):
    tag: str
    method: str
    amount: float
    days: int


def payment_keyboard(amount):
    """Create a payment keyboard with stars"""
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Оплатить {amount} ⭐️", pay=True)
    return builder.as_markup()


class TariffKeyboardBuilder:
    """
    Optimized tariff keyboard builder with caching.
    Reduces redundant calculations and improves memory efficiency.
    """

    def __init__(
            self,
            method: str,
            price: int,
            days: int,
            disc: int,
            currency: str,
            period: str,
            discount_func: Callable[[float, int], float] = None,
            extra_discount: int = 0
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
        :param extra_discount: Дополнительная скидка промокода (%)
        """
        self.method = method
        self.price = price
        self.days = days
        self.disc = disc
        self.currency = currency
        self.period = period
        self.extra_discount = extra_discount
        self.discount_func = discount_func or self.default_discount

    @staticmethod
    def default_discount(amount: float, discount_percent: int) -> float:
        """Стандартная функция расчета скидки"""
        return amount * (1 - discount_percent / 100)

    def calculate_amount(self) -> float:
        """
        Рассчет итоговой суммы с учетом скидки.
        """
        monthly_cost = self.price * (self.days / 30)
        result = self.discount_func(monthly_cost, self.disc)
        if self.extra_discount > 0:
            result = result * (1 - self.extra_discount / 100)
        return result

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
        text = f"{self.period} | {formatted_price} {self.currency}"

        return InlineKeyboardButton(text=text, callback_data=call_data)


class OptimizedTariffKeyboard:
    """
    Optimized tariff keyboard factory with builder pattern.
    Reduces overhead of creating tariff keyboards.
    """

    def __init__(
            self,
            tariff: Dict[str, dict],
            method: str,
            base_price: int,
            discount_func: Optional[Callable[[float, int], float]] = None,
            extra_discount: int = 0
    ):
        """
        Initialize tariff keyboard builder

        :param tariff: Dictionary of tariff definitions
        :param method: Payment method
        :param base_price: Base price
        :param discount_func: Optional discount function
        :param extra_discount: Additional promo discount (%)
        """
        self.tariff = tariff
        self.method = method
        self.base_price = base_price
        self.discount_func = discount_func
        self.extra_discount = extra_discount

    def build(self) -> InlineKeyboardMarkup:
        """Build the complete tariff keyboard"""
        keyboard_buttons = []

        # Add tariff buttons - each on its own row
        for name, params in self.tariff.items():
            days = int(params['days'])
            disc = int(params.get('disc', 0) or 0)
            currency = params['currency']
            period = params['period']

            # If DB provides a direct price, use it
            db_price = params.get('db_price')
            if db_price and db_price > 0:
                amount = db_price
                if self.extra_discount > 0:
                    amount = amount * (1 - self.extra_discount / 100)

                call_data = PaymentCallbackData(
                    tag='data', method=self.method, amount=amount, days=days
                ).pack()
                formatted_price = f"{amount:.2f}".rstrip('0').rstrip('.')
                text = f"{period} | {formatted_price} {currency}"
                keyboard_buttons.append([InlineKeyboardButton(text=text, callback_data=call_data)])
            else:
                tariff_builder = TariffKeyboardBuilder(
                    method=self.method,
                    price=self.base_price,
                    days=days,
                    disc=disc,
                    currency=currency,
                    period=period,
                    discount_func=self.discount_func,
                    extra_discount=self.extra_discount
                )
                button = tariff_builder.build()
                keyboard_buttons.append([button])

        # Add navigation buttons at the bottom
        keyboard_buttons.append([InlineKeyboardButton(text="Назад", callback_data='Premium')])
        keyboard_buttons.append([InlineKeyboardButton(text='На главную', callback_data='Main')])

        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    @staticmethod
    async def from_db(payment_method: str, base_price: int, extra_discount: int = 0) -> Optional[InlineKeyboardMarkup]:
        """Build tariff keyboard from DB data. Returns None if DB has no data."""
        from app.tariffs import get_tariffs_stars_async, get_tariffs_crypto_async, get_tariffs_sbp_async, get_tariffs_crystal_async

        method_map = {
            'stars': get_tariffs_stars_async,
            'crypto': get_tariffs_crypto_async,
            'SBP_APAY': get_tariffs_sbp_async,
            'SBP': get_tariffs_sbp_async,
            'CRYSTAL': get_tariffs_crystal_async,
        }

        getter = method_map.get(payment_method)
        if not getter:
            return None

        tariffs = await getter()
        keyboard = OptimizedTariffKeyboard(
            tariff=tariffs,
            method=payment_method,
            base_price=base_price,
            extra_discount=extra_discount,
        )
        return keyboard.build()

def create_tariff_keyboard(
        tariff: Dict[str, dict],
        method: str,
        base_price: int,
        discount_func: Optional[Callable[[float, int], float]] = None,
        extra_discount: int = 0
) -> InlineKeyboardMarkup:
    """
    Create a tariff keyboard using optimized builder

    :param tariff: Dictionary of tariff definitions
    :param method: Payment method
    :param base_price: Base price
    :param discount_func: Optional discount function
    :param extra_discount: Additional promo discount (%)
    :return: InlineKeyboardMarkup
    """
    keyboard_builder = OptimizedTariffKeyboard(
        tariff=tariff,
        method=method,
        base_price=base_price,
        discount_func=discount_func,
        extra_discount=extra_discount
    )
    return keyboard_builder.build()
