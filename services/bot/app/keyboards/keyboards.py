"""
Keyboard generation module for aiogram.
Static Russian keyboards removed — use localized.py for all user-facing keyboards.
This module retains only shared utilities and backward-compatible lazy accessors.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_connect(link: str) -> InlineKeyboardMarkup:
    """Create a dynamic connect keyboard with link"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Открыть", url=link)
    builder.button(text="На главную", callback_data="Main")
    return builder.as_markup()


def _lazy_inline(*rows):
    """Helper: build InlineKeyboardMarkup from rows of (text, callback_data) tuples."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=c) for t, c in row] for row in rows]
    )


_LAZY_BUILDERS = {
    "subcheck": lambda: _lazy_inline(
        [("Я подписался!", "sub_check")],
        [("На главную", "Main")],
    ),
    "subcheck_free": lambda: _lazy_inline(
        [("Я подписался!", "subcheck_free")],
        [("На главную", "Main")],
    ),
    "to_main": lambda: _lazy_inline([("На главную", "Main")]),
}


def __getattr__(name: str):
    builder = _LAZY_BUILDERS.get(name)
    if builder:
        return builder()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
