"""
Keyboard generation module for aiogram.
Static Russian keyboards removed — use localized.py for all user-facing keyboards.
This module retains only shared utilities and backward-compatible lazy accessors.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.tools import *
from app.tariffs import *
from app.settings import secrets


# ============================================================================
# DYNAMIC KEYBOARDS (parameterized, cannot be in localized.py)
# ============================================================================

def get_connect(link: str) -> InlineKeyboardMarkup:
    """Create a dynamic connect keyboard with link"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Открыть", url=link)
    builder.button(text="На главную", callback_data='Main')
    return builder.as_markup()


# ============================================================================
# TARIFF KEYBOARDS WITH CACHING
# ============================================================================

from functools import lru_cache

@lru_cache(maxsize=5)
def get_starspay_tariffs() -> InlineKeyboardMarkup:
    return create_tariff_keyboard(tariff=tariffs_stars, method='stars', base_price=price_stars)

@lru_cache(maxsize=5)
def get_cryptospay_tariffs() -> InlineKeyboardMarkup:
    return create_tariff_keyboard(tariff=tariffs_crypto, method='crypto', base_price=price_crypto)

@lru_cache(maxsize=5)
def get_sbp_tariffs() -> InlineKeyboardMarkup:
    return create_tariff_keyboard(tariff=tariffs_sbp, method='SBP', base_price=sbp_price)

@lru_cache(maxsize=5)
def get_sbp_apay_tariffs() -> InlineKeyboardMarkup:
    return create_tariff_keyboard(tariff=tariffs_sbp, method='SBP_APAY', base_price=sbp_price)

@lru_cache(maxsize=5)
def get_crystal_tariffs() -> InlineKeyboardMarkup:
    return create_tariff_keyboard(tariff=tariffs_sbp, method='CRYSTAL', base_price=sbp_price)


# ============================================================================
# BACKWARD-COMPATIBLE LAZY ACCESSORS
# These exist so old code like `kb.subcheck` still works.
# All build localized-RU variants; prefer localized.py for new code.
# ============================================================================

def _lazy_inline(*rows):
    """Helper: build InlineKeyboardMarkup from rows of (text, callback_data) tuples."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=c) for t, c in row] for row in rows]
    )

_LAZY_BUILDERS = {
    'subcheck': lambda: _lazy_inline(
        [("Я подписался!", "sub_check")],
        [("На главную", "Main")],
    ),
    'subcheck_free': lambda: _lazy_inline(
        [("Я подписался!", "subcheck_free")],
        [("На главную", "Main")],
    ),
    'to_main': lambda: _lazy_inline([("На главную", "Main")]),
    'pay_extend_month': lambda: _lazy_inline(
        [("🔒Продлить подписку", "Extend_Month")],
        [("На главную", "Main")],
    ),
    'starspay_tariffs': get_starspay_tariffs,
    'cryptospay_tariffs': get_cryptospay_tariffs,
    'sbp_tariffs': get_sbp_tariffs,
    'sbp_apay_tariffs': get_sbp_apay_tariffs,
    'crystal_tariffs': get_crystal_tariffs,
}


def __getattr__(name: str):
    builder = _LAZY_BUILDERS.get(name)
    if builder:
        return builder()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
