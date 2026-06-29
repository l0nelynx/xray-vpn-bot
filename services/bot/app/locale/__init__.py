"""Locale module for multi-language support"""

import app.locale.lang_ru as lang_ru
import app.locale.lang_en as lang_en

_lang_map = {
    "ru": lang_ru,
    "en": lang_en,
}


def get_lang(language: str = "ru"):
    """Get language module by language code"""
    return _lang_map.get(language, lang_ru)
