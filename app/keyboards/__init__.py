from .keyboards import (
    get_buy_from_broadcast,
    get_main_new,
    get_main_pro,
    get_main_free,
    get_others,
    get_pay_methods,
    get_starspay_tariffs,
    get_cryptospay_tariffs,
    get_sbp_tariffs,
    get_sbp_apay_tariffs,
    get_crystal_tariffs,
    get_pay_extend_month,
    get_subcheck,
    get_subcheck_free,
    get_to_main,
    get_agreement_menu,
    get_policy_menu,
    get_cancel_keyboard,
    get_connect,
    KeyboardCache,
)

from .tools import (
    PaymentCallbackData,
    payment_keyboard,
)

# Module-level lazy loading using __getattr__
def __getattr__(name: str):
    """
    Lazy-load keyboards when accessed as module attributes.
    This makes kb.main_pro work correctly.
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

# Export the connect function directly
connect = get_connect
