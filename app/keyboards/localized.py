"""
Localized keyboard generation - creates keyboards with translated button labels.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.settings import secrets


def get_language_select_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard (always same for all languages)"""
    from app.locale import lang_ru
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang_ru.lang_btn_ru, callback_data='set_lang_ru')],
        [InlineKeyboardButton(text=lang_ru.lang_btn_en, callback_data='set_lang_en')],
    ])


def get_main_new_localized(lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang.btn_buy_premium, callback_data='Premium')],
        [InlineKeyboardButton(text=lang.btn_install_instructions, callback_data='Others')],
        [InlineKeyboardButton(text=lang.btn_free_version, callback_data='Free')],
        [InlineKeyboardButton(text=lang.btn_invite_friends, callback_data='Invite_Friends')],
        [InlineKeyboardButton(text=lang.btn_settings, callback_data='Settings')],
    ])


def get_main_pro_localized(lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang.btn_extend_subscription, callback_data='Extend_Month')],
        [InlineKeyboardButton(text=lang.btn_install_instructions, callback_data='Others')],
        [InlineKeyboardButton(text=lang.btn_sub_info, callback_data='Sub_Info')],
        [InlineKeyboardButton(text=lang.btn_devices, callback_data='Devices')],
        [InlineKeyboardButton(text=lang.btn_invite_friends, callback_data='Invite_Friends')],
        [InlineKeyboardButton(text=lang.btn_settings, callback_data='Settings')],
    ])


def get_main_free_localized(lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang.btn_buy_premium, callback_data='Premium')],
        [InlineKeyboardButton(text=lang.btn_install_instructions, callback_data='Others')],
        [InlineKeyboardButton(text=lang.btn_sub_info, callback_data='Sub_Info')],
        [InlineKeyboardButton(text=lang.btn_devices, callback_data='Devices')],
        [InlineKeyboardButton(text=lang.btn_invite_friends, callback_data='Invite_Friends')],
        [InlineKeyboardButton(text=lang.btn_settings, callback_data='Settings')],
    ])


def get_main_marzban_pro_localized(lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang.btn_extend_subscription, callback_data='Extend_Month')],
        [InlineKeyboardButton(text=lang.btn_migrate_beta, callback_data='Migrate_RemnaWave')],
        [InlineKeyboardButton(text=lang.btn_install_instructions, callback_data='Others')],
        [InlineKeyboardButton(text=lang.btn_sub_info, callback_data='Sub_Info')],
        [InlineKeyboardButton(text=lang.btn_invite_friends, callback_data='Invite_Friends')],
        [InlineKeyboardButton(text=lang.btn_settings, callback_data='Settings')],
    ])


def get_main_marzban_free_localized(lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang.btn_buy_premium, callback_data='Premium')],
        [InlineKeyboardButton(text=lang.btn_migrate_beta, callback_data='Migrate_RemnaWave')],
        [InlineKeyboardButton(text=lang.btn_install_instructions, callback_data='Others')],
        [InlineKeyboardButton(text=lang.btn_sub_info, callback_data='Sub_Info')],
        [InlineKeyboardButton(text=lang.btn_invite_friends, callback_data='Invite_Friends')],
        [InlineKeyboardButton(text=lang.btn_settings, callback_data='Settings')],
    ])


def get_others_localized(lang) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang.btn_platform_android, callback_data='Android_Help')
    builder.row()
    builder.button(text=lang.btn_platform_windows, callback_data='Windows_Help')
    builder.row()
    builder.button(text=lang.btn_to_main, callback_data='Main')
    return builder.as_markup()


def get_pay_methods_localized(lang, show_promo: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=lang.btn_pay_stars, callback_data='Stars_Plans')],
        [InlineKeyboardButton(text=lang.btn_pay_crypto, callback_data='Crypto_Plans')],
        [InlineKeyboardButton(text=lang.btn_pay_crystal, callback_data='Crystal_plans')],
        [InlineKeyboardButton(text=lang.btn_pay_card, callback_data='SBP_Apay')],
    ]
    if show_promo:
        buttons.append([InlineKeyboardButton(text=lang.btn_have_promo, callback_data='Enter_Promo')])
    buttons.append([InlineKeyboardButton(text=lang.btn_back, callback_data='Main')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_to_main_localized(lang) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang.btn_to_main, callback_data='Main')
    return builder.as_markup()


def get_connect_localized(lang, link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang.btn_open, url=link)
    builder.button(text=lang.btn_to_main, callback_data='Main')
    return builder.as_markup()


def get_subcheck_free_localized(lang) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang.btn_i_subscribed, callback_data='subcheck_free')
    builder.row()
    builder.button(text=lang.btn_to_main, callback_data='Main')
    return builder.as_markup()


def get_agreement_menu_localized(lang) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang.btn_full_text, web_app=WebAppInfo(url=secrets.get('agreement_url')))
    builder.row()
    builder.button(text=lang.btn_back, callback_data='Settings')
    return builder.as_markup()


def get_policy_menu_localized(lang) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang.btn_full_text, web_app=WebAppInfo(url=secrets.get('policy_url')))
    builder.row()
    builder.button(text=lang.btn_back, callback_data='Settings')
    return builder.as_markup()


def get_migration_confirm_localized(lang) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang.btn_confirm_migration, callback_data='confirm_migrate')
    builder.row()
    builder.button(text=lang.btn_cancel, callback_data='Main')
    return builder.as_markup()


def get_limited_menu_localized(lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang.btn_buy_premium_short, callback_data='Premium')],
        [InlineKeyboardButton(text=lang.btn_to_main, callback_data='Main')],
    ])


def get_settings_menu_localized(lang) -> InlineKeyboardMarkup:
    """Settings menu with Language, Agreement, Privacy and back button"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang.btn_language, callback_data='Change_Language')],
        [InlineKeyboardButton(text=lang.btn_user_agreement, callback_data='Agreement')],
        [InlineKeyboardButton(text=lang.btn_privacy_policy, callback_data='Privacy')],
        [InlineKeyboardButton(text=lang.btn_to_main, callback_data='Main')],
    ])


def get_language_change_keyboard(lang) -> InlineKeyboardMarkup:
    """Language selection keyboard shown from Settings, with back to Settings"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang.lang_btn_ru, callback_data='set_lang_ru')],
        [InlineKeyboardButton(text=lang.lang_btn_en, callback_data='set_lang_en')],
        [InlineKeyboardButton(text=lang.btn_back, callback_data='Settings')],
    ])


def get_pay_extend_month_localized(lang) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang.btn_extend_subscription, callback_data='Extend_Month')
    builder.row()
    builder.button(text=lang.btn_to_main, callback_data='Main')
    return builder.as_markup()
