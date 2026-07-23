"""Tariff data getters — Dashboard tariff_plans / tariff_prices only (no YAML prices)."""
from app.database.tariff_repository import get_tariffs_for_method


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
    return _db_to_legacy(db, lang) if db else {}


async def get_tariffs_crypto_async(lang: str = "ru"):
    db = await get_tariffs_for_method("crypto")
    return _db_to_legacy(db, lang) if db else {}


async def get_tariffs_sbp_async(lang: str = "ru"):
    db = await get_tariffs_for_method("SBP_APAY")
    return _db_to_legacy(db, lang) if db else {}


async def get_tariffs_crystal_async(lang: str = "ru"):
    db = await get_tariffs_for_method("CRYSTAL")
    return _db_to_legacy(db, lang) if db else {}
