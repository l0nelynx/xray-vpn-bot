"""Tariff keyboard builders (optimised, with caching) for the bot constructor."""
from typing import Callable, Dict, Optional

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class PaymentCallbackData(CallbackData, prefix=""):
    tag: str
    method: str
    amount: float
    days: int


class CreditsNodeCallbackData(CallbackData, prefix="crd"):
    node_id: int


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
        discount_func: Callable[[float, int], float] = None,
        extra_discount: int = 0,
    ):
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
        return amount * (1 - discount_percent / 100)

    def calculate_amount(self) -> float:
        monthly_cost = self.price * (self.days / 30)
        result = self.discount_func(monthly_cost, self.disc)
        if self.extra_discount > 0:
            result = result * (1 - self.extra_discount / 100)
        return result

    def build(self) -> InlineKeyboardButton:
        amount = self.calculate_amount()
        call_data = PaymentCallbackData(
            tag="data", method=self.method, amount=amount, days=self.days
        ).pack()
        formatted_price = f"{amount:.2f}".rstrip("0").rstrip(".")
        text = f"{self.period} | {formatted_price} {self.currency}"
        return InlineKeyboardButton(text=text, callback_data=call_data)


class OptimizedTariffKeyboard:
    def __init__(
        self,
        tariff: Dict[str, dict],
        method: str,
        discount_func: Optional[Callable[[float, int], float]] = None,
        extra_discount: int = 0,
        lang: str = "ru",
    ):
        self.tariff = tariff
        self.method = method
        self.discount_func = discount_func
        self.extra_discount = extra_discount
        self.lang = lang

    def build(self) -> InlineKeyboardMarkup:
        keyboard_buttons = []
        for name, params in self.tariff.items():
            days = int(params["days"])
            currency = params["currency"]
            period = params["period"]

            db_price = params.get("db_price")
            if not db_price or db_price <= 0:
                continue
            amount = db_price
            if self.extra_discount > 0:
                amount = amount * (1 - self.extra_discount / 100)
            call_data = PaymentCallbackData(
                tag="data", method=self.method, amount=amount, days=days
            ).pack()
            formatted_price = f"{amount:.2f}".rstrip("0").rstrip(".")
            text = f"{period} | {formatted_price} {currency}"
            keyboard_buttons.append([InlineKeyboardButton(text=text, callback_data=call_data)])

        back_text = "Back" if self.lang == "en" else "Назад"
        main_text = "Main menu" if self.lang == "en" else "На главную"
        keyboard_buttons.append([InlineKeyboardButton(text=back_text, callback_data="Premium")])
        keyboard_buttons.append([InlineKeyboardButton(text=main_text, callback_data="Main")])
        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    @staticmethod
    async def from_db(
        payment_method: str,
        extra_discount: int = 0,
        lang: str = "ru",
    ) -> Optional[InlineKeyboardMarkup]:
        from app.bot_constructor.tariffs import (
            get_tariffs_crystal_async,
            get_tariffs_crypto_async,
            get_tariffs_sbp_async,
            get_tariffs_stars_async,
        )

        method_map = {
            "stars": get_tariffs_stars_async,
            "crypto": get_tariffs_crypto_async,
            "SBP_APAY": get_tariffs_sbp_async,
            "SBP": get_tariffs_sbp_async,
            "CRYSTAL": get_tariffs_crystal_async,
        }
        getter = method_map.get(payment_method)
        if not getter:
            return None
        tariffs = await getter(lang=lang)
        if not tariffs:
            return None
        return OptimizedTariffKeyboard(
            tariff=tariffs,
            method=payment_method,
            extra_discount=extra_discount,
            lang=lang,
        ).build()


def create_tariff_keyboard(
    tariff: Dict[str, dict],
    method: str,
    discount_func: Optional[Callable[[float, int], float]] = None,
    extra_discount: int = 0,
) -> InlineKeyboardMarkup:
    return OptimizedTariffKeyboard(
        tariff=tariff,
        method=method,
        discount_func=discount_func,
        extra_discount=extra_discount,
    ).build()
