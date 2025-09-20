from app.keyboards.buttons import *
from app.keyboards.tools import *
from app.tariffs import *

buy_from_broadcast = InlineKeyboardMarkup(inline_keyboard=[[premium_button],
                                                           #  [howto_button],
                                                           [subcheck_button]])

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
                                               [windows_button],
                                               # [ios_button],
                                               # [win_button],
                                               # [linux_button],
                                               [to_main_button]])

pay_methods = InlineKeyboardMarkup(inline_keyboard=[[paystars_button],
                                                    [paycryptobot_button],
                                                    [crystal_button],
                                                    # [paysbp_button],
                                                    [apays_button],
                                                    [to_main_button]])

starspay_tariffs = create_tariff_keyboard(tariff=tariffs_stars, method='stars', base_price=price_stars)

cryptospay_tariffs = create_tariff_keyboard(tariff=tariffs_crypto, method='crypto', base_price=price_crypto)

sbp_tariffs = create_tariff_keyboard(tariff=tariffs_sbp, method='SBP', base_price=sbp_price)

sbp_apay_tariffs = create_tariff_keyboard(tariff=tariffs_sbp, method='SBP_APAY', base_price=sbp_price)

crystal_tariffs = create_tariff_keyboard(tariff=tariffs_sbp, method='CRYSTAL', base_price=sbp_price)

pay_extend_month = InlineKeyboardMarkup(inline_keyboard=[[extend_button],
                                                         [to_main_button]])
subcheck = InlineKeyboardMarkup(inline_keyboard=[[subcheck_button],
                                                 [to_main_button]])

to_main = InlineKeyboardMarkup(inline_keyboard=[[to_main_button]])

agreement_menu = InlineKeyboardMarkup(inline_keyboard=[
    to_web_info_button(secrets.get('agreement_url'), "Полный текст"),
    [to_main_button]])

policy_menu = InlineKeyboardMarkup(inline_keyboard=[
    to_web_info_button(secrets.get('policy_url'), "Полный текст"),
    [to_main_button]])


def connect(link):
    return InlineKeyboardMarkup(inline_keyboard=[to_web_info_button(link, "Подробнее"),
                                                 [to_main_button]])


# Создаем клавиатуру с кнопкой отмены
cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[[cancel_broadcast_button]])
