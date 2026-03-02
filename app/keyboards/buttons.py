"""
Optimized button factory module for aiogram keyboards.
Uses factory patterns to avoid repetitive button definitions.
"""
from typing import Callable
from aiogram.types import InlineKeyboardButton, WebAppInfo


class ButtonFactory:
    """Factory for creating consistent button types"""

    @staticmethod
    def callback_button(text: str, callback_data: str) -> InlineKeyboardButton:
        """Create a callback button"""
        return InlineKeyboardButton(text=text, callback_data=callback_data)

    @staticmethod
    def url_button(text: str, url: str) -> InlineKeyboardButton:
        """Create a URL button"""
        return InlineKeyboardButton(text=text, url=url)

    @staticmethod
    def web_app_button(text: str, web_app_url: str) -> InlineKeyboardButton:
        """Create a WebApp button"""
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=web_app_url))

    @staticmethod
    def pay_button(text: str = "Оплатить") -> InlineKeyboardButton:
        """Create a payment button"""
        return InlineKeyboardButton(text=text, pay=True)


class ButtonDefinitions:
    """Centralized button definitions using factory patterns"""

    # Payment Method Buttons
    PAYMENT_METHODS = {
        'stars': ('🔒Telegram Stars⭐️', 'Stars_Plans'),
        'crypto': ('🔒CryptoBot⭐️', 'Crypto_Plans'),
        'sbp': ('🔒СБП⭐️', 'SBP_Plans'),
        'apay': ('🔒Банковская карта/перевод⭐️', 'SBP_Apay'),
        'crystal': ('🔒Криптовалюта⭐️', 'Crystal_plans'),
    }

    # Main Menu Buttons
    MAIN_MENU = {
        'premium': ('🔒Приобрести CheezeVPN Premium⭐️', 'Premium'),
        'extend': ('🔒Продлить подписку', 'Extend_Month'),
        'status': ('Информация о подписке', 'Sub_Info'),
        'howto': ('Инструкция по установке', 'Others'),
        'free': ('Бесплатная версия', 'Free'),
    }

    # Help/Setup Buttons
    HELP = {
        'android': ('Android/IOS - Happ', 'Android_Help'),
        'windows': ('Windows/Linux - Throne', 'Windows_Help'),
    }

    # Legal Buttons
    LEGAL = {
        'agreement': ('Пользовательское соглашение', 'Agreement'),
        'privacy': ('Политика конфиденциальности', 'Privacy'),
    }

    # Navigation Buttons
    NAVIGATION = {
        'back': ('Назад', 'Premium'),
        'to_main': ('На главную', 'Main'),
        'cancel': ('Отменить рассылку', 'cancel_broadcast'),
    }

    # Subscription Buttons
    SUBSCRIPTION = {
        'check': ('Я подписался!', 'sub_check'),
        'check_free': ('Я подписался!', 'subcheck_free'),
    }

    @classmethod
    def get_button(cls, category: str, name: str) -> InlineKeyboardButton:
        """
        Get a button by category and name

        Args:
            category: Button category (e.g., 'PAYMENT_METHODS', 'MAIN_MENU')
            name: Button name within category

        Returns:
            InlineKeyboardButton
        """
        button_dict = getattr(cls, category)
        text, callback_data = button_dict[name]
        return ButtonFactory.callback_button(text, callback_data)

    @classmethod
    def get_url_button(cls, text: str, url: str) -> InlineKeyboardButton:
        """Get a URL button"""
        return ButtonFactory.url_button(text, url)

    @classmethod
    def get_web_app_button(cls, text: str, url: str) -> InlineKeyboardButton:
        """Get a WebApp button"""
        return ButtonFactory.web_app_button(text, url)


# Legacy compatibility - create buttons on demand instead of at module load
def get_button(category: str, name: str) -> InlineKeyboardButton:
    """Compatibility function for backward compatibility"""
    return ButtonDefinitions.get_button(category, name)


# For direct access (backward compatible with old code)
paystars_button = ButtonFactory.callback_button('🔒Telegram Stars⭐️', 'Stars_Plans')
paycryptobot_button = ButtonFactory.callback_button('🔒CryptoBot⭐️', 'Crypto_Plans')
paysbp_button = ButtonFactory.callback_button('🔒СБП⭐️', 'SBP_Plans')
apays_button = ButtonFactory.callback_button('🔒Банковская карта/перевод⭐️', 'SBP_Apay')
crystal_button = ButtonFactory.callback_button('🔒Криптовалюта⭐️', 'Crystal_plans')
to_pay_method_back = ButtonFactory.callback_button('Назад', 'Premium')
premium_button = ButtonFactory.callback_button('🔒Приобрести CheezeVPN Premium⭐️', 'Premium')
extend_button = ButtonFactory.callback_button('🔒Продлить подписку', 'Extend_Month')
status_button = ButtonFactory.callback_button('Информация о подписке', 'Sub_Info')
howto_button = ButtonFactory.callback_button('Инструкция по установке', 'Others')
free_button = ButtonFactory.callback_button('Бесплатная версия', 'Free')
android_button = ButtonFactory.callback_button('Android/IOS - Happ', 'Android_Help')
windows_button = ButtonFactory.callback_button('Windows/Linux - Throne', 'Windows_Help')
to_main_button = ButtonFactory.callback_button('На главную', 'Main')
agreement_button = ButtonFactory.callback_button('Пользовательское соглашение', 'Agreement')
privacy_button = ButtonFactory.callback_button('Политика конфиденциальности', 'Privacy')
subcheck_button = ButtonFactory.callback_button('Я подписался!', 'sub_check')
subcheck_free_button = ButtonFactory.callback_button('Я подписался!', 'subcheck_free')
cancel_broadcast_button = ButtonFactory.callback_button('Отменить рассылку', 'cancel_broadcast')

