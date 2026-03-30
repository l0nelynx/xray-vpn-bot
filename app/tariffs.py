from app.settings import secrets
from app.database.tariff_repository import get_tariffs_for_method


def _disc():
    return str(secrets.get('discount', 0))


# ---- Hardcoded fallbacks (used when DB is empty) ----

def _fallback_stars():
    return {
        'month': {'days': '30', 'disc': '0', 'currency': '⭐️', 'period': '1 Месяц'},
        '3 month': {'days': '90', 'disc': _disc(), 'currency': '⭐️', 'period': '3 Месяца'},
        '12 month': {'days': '360', 'disc': _disc(), 'currency': '⭐️', 'period': 'Год'},
    }


def _fallback_crypto():
    return {
        'month': {'days': '30', 'disc': '0', 'currency': 'USDT', 'period': '1 Месяц'},
        '3 month': {'days': '90', 'disc': _disc(), 'currency': 'USDT', 'period': '3 Месяца'},
        '12 month': {'days': '360', 'disc': _disc(), 'currency': 'USDT', 'period': 'Год'},
    }


def _fallback_sbp():
    return {
        'month': {'days': '30', 'disc': '0', 'currency': 'RUB', 'period': '1 Месяц'},
        '3 month': {'days': '90', 'disc': _disc(), 'currency': 'RUB', 'period': '3 Месяца'},
        '12 month': {'days': '360', 'disc': _disc(), 'currency': 'RUB', 'period': 'Год'},
    }


def _db_to_legacy(db_tariffs: list[dict]) -> dict:
    """Convert DB tariff list to legacy dict format."""
    result = {}
    for t in db_tariffs:
        key = t["slug"]
        result[key] = {
            'days': str(t['days']),
            'disc': str(t.get('discount_percent', 0)),
            'currency': t['currency'],
            'period': t['name_ru'],
            'db_price': t.get('price'),  # direct price from DB
        }
    return result


# ---- Async DB-backed getters ----

async def get_tariffs_stars_async():
    db = await get_tariffs_for_method('stars')
    if db:
        return _db_to_legacy(db)
    return _fallback_stars()


async def get_tariffs_crypto_async():
    db = await get_tariffs_for_method('crypto')
    if db:
        return _db_to_legacy(db)
    return _fallback_crypto()


async def get_tariffs_sbp_async():
    db = await get_tariffs_for_method('SBP_APAY')
    if db:
        return _db_to_legacy(db)
    return _fallback_sbp()


async def get_tariffs_crystal_async():
    db = await get_tariffs_for_method('CRYSTAL')
    if db:
        return _db_to_legacy(db)
    return _fallback_sbp()


# ---- Sync wrappers (backward compatibility) ----

def get_tariffs_stars():
    return _fallback_stars()


def get_tariffs_crypto():
    return _fallback_crypto()


def get_tariffs_sbp():
    return _fallback_sbp()


# Backward compatibility via __getattr__
def __getattr__(name):
    _map = {
        'tariffs_stars': get_tariffs_stars,
        'tariffs_crypto': get_tariffs_crypto,
        'tariffs_sbp': get_tariffs_sbp,
    }
    if name in _map:
        return _map[name]()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
