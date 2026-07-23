""" Backward-compatibility shim — real implementation moved to app.bot_constructor.tariffs."""
from app.bot_constructor.tariffs import (  # noqa: F401
    get_tariffs_stars_async,
    get_tariffs_crypto_async,
    get_tariffs_sbp_async,
    get_tariffs_crystal_async,
    _db_to_legacy,
)
