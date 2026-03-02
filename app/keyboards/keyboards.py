"""
Optimized keyboard generation module for aiogram.
Implements lazy-loading, caching, and efficient keyboard building.
"""
from functools import lru_cache
from typing import Dict, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.buttons import *
from app.keyboards.tools import *
from app.tariffs import *
from app.settings import secrets


class KeyboardCache:
    """
    Simple keyboard cache to avoid recreating static keyboards repeatedly.
    Reduces memory allocation and improves response times.
    """
    _cache: Dict[str, InlineKeyboardMarkup] = {}

    @classmethod
    def get(cls, key: str) -> Optional[InlineKeyboardMarkup]:
        """Get cached keyboard"""
        return cls._cache.get(key)

    @classmethod
    def set(cls, key: str, keyboard: InlineKeyboardMarkup) -> None:
        """Cache a keyboard"""
        cls._cache[key] = keyboard

    @classmethod
    def clear(cls) -> None:
        """Clear all cached keyboards"""
        cls._cache.clear()


# ============================================================================
# STATIC KEYBOARDS WITH LAZY LOADING
# ============================================================================

def get_buy_from_broadcast() -> InlineKeyboardMarkup:
    """Lazy-loaded broadcast purchase keyboard"""
    key = 'buy_from_broadcast'
    cached = KeyboardCache.get(key)
    if cached:
        return cached

    builder = InlineKeyboardBuilder()
    builder.button(text="Приобрести подписку", url=secrets.get('bot_url'))
    keyboard = builder.as_markup()
    KeyboardCache.set(key, keyboard)
    return keyboard


def get_main_new() -> InlineKeyboardMarkup:
    """Lazy-loaded main menu for new users"""
    key = 'main_new'
    cached = KeyboardCache.get(key)
    if cached:
        return cached

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒Приобрести CheezeVPN Premium⭐️", callback_data='Premium')],
        [InlineKeyboardButton(text="Инструкция по установке", callback_data='Others')],
        [InlineKeyboardButton(text="Бесплатная версия", callback_data='Free')],
        [InlineKeyboardButton(text="Пользовательское соглашение", callback_data='Agreement')],
        [InlineKeyboardButton(text="Политика конфиденциальности", callback_data='Privacy')],
    ])
    KeyboardCache.set(key, keyboard)
    return keyboard


def get_main_pro() -> InlineKeyboardMarkup:
    """Lazy-loaded main menu for premium users"""
    key = 'main_pro'
    cached = KeyboardCache.get(key)
    if cached:
        return cached

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒Продлить подписку", callback_data='Extend_Month')],
        [InlineKeyboardButton(text="Инструкция по установке", callback_data='Others')],
        [InlineKeyboardButton(text="Информация о подписке", callback_data='Sub_Info')],
        [InlineKeyboardButton(text="Пользовательское соглашение", callback_data='Agreement')],
        [InlineKeyboardButton(text="Политика конфиденциальности", callback_data='Privacy')],
    ])
    KeyboardCache.set(key, keyboard)
    return keyboard


def get_main_free() -> InlineKeyboardMarkup:
    """Lazy-loaded main menu for free users"""
    key = 'main_free'
    cached = KeyboardCache.get(key)
    if cached:
        return cached

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒Приобрести CheezeVPN Premium⭐️", callback_data='Premium')],
        [InlineKeyboardButton(text="Инструкция по установке", callback_data='Others')],
        [InlineKeyboardButton(text="Информация о подписке", callback_data='Sub_Info')],
        [InlineKeyboardButton(text="Пользовательское соглашение", callback_data='Agreement')],
        [InlineKeyboardButton(text="Политика конфиденциальности", callback_data='Privacy')],
    ])
    KeyboardCache.set(key, keyboard)
    return keyboard


def get_others() -> InlineKeyboardMarkup:
    """Lazy-loaded help/setup menu"""
    key = 'others'
    cached = KeyboardCache.get(key)
    if cached:
        return cached

    builder = InlineKeyboardBuilder()
    builder.button(text="Android/IOS - Happ", callback_data='Android_Help')
    builder.row()
    builder.button(text="Windows/Linux - Throne", callback_data='Windows_Help')
    builder.row()
    builder.button(text="На главную", callback_data='Main')
    keyboard = builder.as_markup()
    KeyboardCache.set(key, keyboard)
    return keyboard


def get_pay_methods() -> InlineKeyboardMarkup:
    """Lazy-loaded payment methods menu"""
    key = 'pay_methods'
    cached = KeyboardCache.get(key)
    if cached:
        return cached

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data='Stars_Plans')],
        [InlineKeyboardButton(text="💰 CryptoBot", callback_data='Crypto_Plans')],
        [InlineKeyboardButton(text="🔷 Crystal Pay", callback_data='Crystal_plans')],
        [InlineKeyboardButton(text="💳 Банковская карта", callback_data='SBP_Apay')],
        [InlineKeyboardButton(text="◀️ Назад", callback_data='Main')],
    ])
    KeyboardCache.set(key, keyboard)
    return keyboard


def get_pay_extend_month() -> InlineKeyboardMarkup:
    """Lazy-loaded extend subscription menu"""
    key = 'pay_extend_month'
    cached = KeyboardCache.get(key)
    if cached:
        return cached

    builder = InlineKeyboardBuilder()
    builder.button(text="🔒Продлить подписку", callback_data='Extend_Month')
    builder.row()
    builder.button(text="На главную", callback_data='Main')
    keyboard = builder.as_markup()
    KeyboardCache.set(key, keyboard)
    return keyboard


def get_subcheck() -> InlineKeyboardMarkup:
    """Lazy-loaded subscription check menu"""
    key = 'subcheck'
    cached = KeyboardCache.get(key)
    if cached:
        return cached

    builder = InlineKeyboardBuilder()
    builder.button(text="Я подписался!", callback_data='sub_check')
    builder.row()
    builder.button(text="На главную", callback_data='Main')
    keyboard = builder.as_markup()
    KeyboardCache.set(key, keyboard)
    return keyboard


def get_subcheck_free() -> InlineKeyboardMarkup:
    """Lazy-loaded free subscription check menu"""
    key = 'subcheck_free'
    cached = KeyboardCache.get(key)
    if cached:
        return cached

    builder = InlineKeyboardBuilder()
    builder.button(text="Я подписался!", callback_data='subcheck_free')
    builder.row()
    builder.button(text="На главную", callback_data='Main')
    keyboard = builder.as_markup()
    KeyboardCache.set(key, keyboard)
    return keyboard


def get_to_main() -> InlineKeyboardMarkup:
    """Lazy-loaded simple main menu button"""
    key = 'to_main'
    cached = KeyboardCache.get(key)
    if cached:
        return cached

    builder = InlineKeyboardBuilder()
    builder.button(text="На главную", callback_data='Main')
    keyboard = builder.as_markup()
    KeyboardCache.set(key, keyboard)
    return keyboard


def get_agreement_menu() -> InlineKeyboardMarkup:
    """Lazy-loaded agreement menu"""
    key = 'agreement_menu'
    cached = KeyboardCache.get(key)
    if cached:
        return cached

    builder = InlineKeyboardBuilder()
    builder.button(text="Полный текст", web_app=WebAppInfo(url=secrets.get('agreement_url')))
    builder.row()
    builder.button(text="На главную", callback_data='Main')
    keyboard = builder.as_markup()
    KeyboardCache.set(key, keyboard)
    return keyboard


def get_policy_menu() -> InlineKeyboardMarkup:
    """Lazy-loaded privacy policy menu"""
    key = 'policy_menu'
    cached = KeyboardCache.get(key)
    if cached:
        return cached

    builder = InlineKeyboardBuilder()
    builder.button(text="Полный текст", web_app=WebAppInfo(url=secrets.get('policy_url')))
    builder.row()
    builder.button(text="На главную", callback_data='Main')
    keyboard = builder.as_markup()
    KeyboardCache.set(key, keyboard)
    return keyboard


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Lazy-loaded cancel broadcast keyboard"""
    key = 'cancel_keyboard'
    cached = KeyboardCache.get(key)
    if cached:
        return cached

    builder = InlineKeyboardBuilder()
    builder.button(text="Отменить рассылку", callback_data='cancel_broadcast')
    keyboard = builder.as_markup()
    KeyboardCache.set(key, keyboard)
    return keyboard


# ============================================================================
# DYNAMIC KEYBOARDS
# ============================================================================

def get_connect(link: str) -> InlineKeyboardMarkup:
    """
    Create a dynamic connect keyboard with link

    Args:
        link: URL to connect

    Returns:
        InlineKeyboardMarkup with connect button
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Подробнее", url=link)
    builder.button(text="На главную", callback_data='Main')
    return builder.as_markup()


# ============================================================================
# TARIFF KEYBOARDS WITH CACHING
# ============================================================================

@lru_cache(maxsize=5)
def get_starspay_tariffs() -> InlineKeyboardMarkup:
    """Get Telegram Stars tariff keyboard (cached)"""
    return create_tariff_keyboard(tariff=tariffs_stars, method='stars', base_price=price_stars)


@lru_cache(maxsize=5)
def get_cryptospay_tariffs() -> InlineKeyboardMarkup:
    """Get CryptoBot tariff keyboard (cached)"""
    return create_tariff_keyboard(tariff=tariffs_crypto, method='crypto', base_price=price_crypto)


@lru_cache(maxsize=5)
def get_sbp_tariffs() -> InlineKeyboardMarkup:
    """Get SBP tariff keyboard (cached)"""
    return create_tariff_keyboard(tariff=tariffs_sbp, method='SBP', base_price=sbp_price)


@lru_cache(maxsize=5)
def get_sbp_apay_tariffs() -> InlineKeyboardMarkup:
    """Get SBP APAY tariff keyboard (cached)"""
    return create_tariff_keyboard(tariff=tariffs_sbp, method='SBP_APAY', base_price=sbp_price)


@lru_cache(maxsize=5)
def get_crystal_tariffs() -> InlineKeyboardMarkup:
    """Get Crystal Pay tariff keyboard (cached)"""
    return create_tariff_keyboard(tariff=tariffs_sbp, method='CRYSTAL', base_price=sbp_price)


# ============================================================================
# BACKWARD COMPATIBILITY - Expose as module attributes
# ============================================================================

# These will be replaced with lazy-loading functions on first access
buy_from_broadcast = None
main_new = None
main_pro = None
main_free = None
others = None
pay_methods = None
starspay_tariffs = None
cryptospay_tariffs = None
sbp_tariffs = None
sbp_apay_tariffs = None
crystal_tariffs = None
pay_extend_month = None
subcheck = None
subcheck_free = None
to_main = None
agreement_menu = None
policy_menu = None
cancel_keyboard = None


def __getattr__(name: str):
    """
    Lazy-load keyboards when accessed as module attributes.
    This provides backward compatibility while implementing lazy loading.
    """
    lazy_keyboards = {
        'buy_from_broadcast': get_buy_from_broadcast,
        'main_new': get_main_new,
        'main_pro': get_main_pro,
        'main_free': get_main_free,
        'others': get_others,
        'pay_methods': get_pay_methods,
        'starspay_tariffs': get_starspay_tariffs,
        'cryptospay_tariffs': get_cryptospay_tariffs,
        'sbp_tariffs': get_sbp_tariffs,
        'sbp_apay_tariffs': get_sbp_apay_tariffs,
        'crystal_tariffs': get_crystal_tariffs,
        'pay_extend_month': get_pay_extend_month,
        'subcheck': get_subcheck,
        'subcheck_free': get_subcheck_free,
        'to_main': get_to_main,
        'agreement_menu': get_agreement_menu,
        'policy_menu': get_policy_menu,
        'cancel_keyboard': get_cancel_keyboard,
    }

    if name in lazy_keyboards:
        return lazy_keyboards[name]()

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
