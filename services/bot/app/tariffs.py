"""Backward-compatibility shim — real implementation moved to app.bot_constructor.tariffs."""
from app.bot_constructor.tariffs import (  # noqa: F401
    get_tariffs_stars_async,
    get_tariffs_crypto_async,
    get_tariffs_sbp_async,
    get_tariffs_crystal_async,
    get_tariffs_stars,
    get_tariffs_crypto,
    get_tariffs_sbp,
    _fallback_stars,
    _fallback_crypto,
    _fallback_sbp,
    _db_to_legacy,
)


def __getattr__(name):
    _map = {
        "tariffs_stars": get_tariffs_stars,
        "tariffs_crypto": get_tariffs_crypto,
        "tariffs_sbp": get_tariffs_sbp,
    }
    if name in _map:
        return _map[name]()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
