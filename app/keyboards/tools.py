"""
Optimized keyboard tools module for aiogram.
Implements efficient tariff keyboard building with caching and performance improvements.
"""
from typing import Callable, Dict, Optional
from functools import lru_cache

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
    """Create a payment keyboard with stars"""
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Оплатить {amount} ⭐️", pay=True)
    return builder.as_markup()


class TariffKeyboardBuilder:
    """
    Optimized tariff keyboard builder with caching.
    Reduces redundant calculations and improves memory efficiency.
    """

    # Cache for calculated amounts to avoid recalculation
    _amount_cache: Dict[tuple, float] = {}

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
        Implements caching to avoid recalculation of identical parameters.
        """
        cache_key = (self.price, self.days, self.disc, self.extra_discount)

        # Check cache first
        if cache_key in self._amount_cache:
            return self._amount_cache[cache_key]

        monthly_cost = self.price * (self.days / 30)
        result = self.discount_func(monthly_cost, self.disc)
        if self.extra_discount > 0:
            result = result * (1 - self.extra_discount / 100)

        # Cache the result
        self._amount_cache[cache_key] = result
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
        text = f"🔒БЕЗЛИМИТ - {self.period} | {formatted_price} {self.currency}"

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
            disc = int(params['disc'])
            currency = params['currency']
            period = params['period']

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
            keyboard_buttons.append([button])  # Each button in its own row

        # Add navigation buttons at the bottom
        keyboard_buttons.append([InlineKeyboardButton(text="Назад", callback_data='Premium')])
        keyboard_buttons.append([InlineKeyboardButton(text='На главную', callback_data='Main')])

        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    @staticmethod
    def _get_button_text(tariff_builder: TariffKeyboardBuilder) -> str:
        """Extract button text from tariff builder"""
        amount = tariff_builder.calculate_amount()
        formatted_price = f"{amount:.2f}".rstrip('0').rstrip('.')
        return f"🔒БЕЗЛИМИТ - {tariff_builder.period} | {formatted_price} {tariff_builder.currency}"


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


# ============================================================================
# UTILITY FUNCTIONS FOR BACKWARD COMPATIBILITY
# ============================================================================

def to_web_info_button(link: str, text: str) -> list:
    """Create a WebApp button (backward compatible)"""
    return [InlineKeyboardButton(text=text, web_app=__import__('aiogram.types', fromlist=['WebAppInfo']).WebAppInfo(url=link))]


def to_url_button(link: str, text: str) -> list:
    """Create a URL button (backward compatible)"""
    return [InlineKeyboardButton(text=text, url=link)]
