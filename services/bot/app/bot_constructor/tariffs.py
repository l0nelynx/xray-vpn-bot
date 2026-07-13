"""Tariff data getters with async DB access and sync fallback to config.yml prices."""
from app.settings import secrets
from app.database.tariff_repository import get_tariffs_for_method


def _disc():
    return str(secrets.get("discount", 0))


def _fallback_stars():
    return {
        "month": {"days": "30", "disc": "0", "currency": "⭐️", "period": "1 Месяц"},
        "3 month": {"days": "90", "disc": _disc(), "currency": "⭐️", "period": "3 Месяца"},
        "12 month": {"days": "360", "disc": _disc(), "currency": "⭐️", "period": "Год"},
    }


def _fallback_crypto():
    return {
        "month": {"days": "30", "disc": "0", "currency": "USDT", "period": "1 Месяц"},
        "3 month": {"days": "90", "disc": _disc(), "currency": "USDT", "period": "3 Месяца"},
        "12 month": {"days": "360", "disc": _disc(), "currency": "USDT", "period": "Год"},
    }


def _fallback_sbp():
    return {
        "month": {"days": "30", "disc": "0", "currency": "RUB", "period": "1 Месяц"},
        "3 month": {"days": "90", "disc": _disc(), "currency": "RUB", "period": "3 Месяца"},
        "12 month": {"days": "360", "disc": _disc(), "currency": "RUB", "period": "Год"},
    }


def _db_to_legacy(db_tariffs: list[dict], lang: str = "ru") -> dict:
    result = {}
    for t in db_tariffs:
        result[t["slug"]] = {
            "days": str(t["days"]),
            "disc": str(t.get("discount_percent", 0)),
            "currency": t["currency"],
            "period": t["name_en"] if lang == "en" else t["name_ru"],
            "db_price": t.get("price"),
            "squad_id": t.get("squad_id"),
            "external_squad_id": t.get("external_squad_id"),
        }
    return result


async def get_tariffs_stars_async(lang: str = "ru"):
    db = await get_tariffs_for_method("stars")
    return _db_to_legacy(db, lang) if db else _fallback_stars()


async def get_tariffs_crypto_async(lang: str = "ru"):
    db = await get_tariffs_for_method("crypto")
    return _db_to_legacy(db, lang) if db else _fallback_crypto()


async def get_tariffs_sbp_async(lang: str = "ru"):
    db = await get_tariffs_for_method("SBP_APAY")
    return _db_to_legacy(db, lang) if db else _fallback_sbp()


async def get_tariffs_crystal_async(lang: str = "ru"):
    db = await get_tariffs_for_method("CRYSTAL")
    return _db_to_legacy(db, lang) if db else _fallback_sbp()


def get_tariffs_stars():
    return _fallback_stars()


def get_tariffs_crypto():
    return _fallback_crypto()


def get_tariffs_sbp():
    return _fallback_sbp()
