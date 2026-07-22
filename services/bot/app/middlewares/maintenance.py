"""Maintenance-mode gate for Telegram updates (admin bypass)."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from common_db.runtime_config import get_maintenance, is_maintenance_enabled


class MaintenanceMiddleware(BaseMiddleware):
    """Block non-admin users while runtime maintenance.enabled is true."""

    def __init__(self, admin_id: int | None):
        self._admin_id = int(admin_id) if admin_id is not None else None

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not is_maintenance_enabled():
            return await handler(event, data)

        user = data.get("event_from_user")
        user_id = getattr(user, "id", None) if user is not None else None
        if self._admin_id is not None and user_id == self._admin_id:
            return await handler(event, data)

        maint = get_maintenance()
        title = maint.get("title") or "Технические работы"
        text = maint.get("text") or "Сервис временно недоступен."
        body = f"<b>{title}</b>\n\n{text}"

        if isinstance(event, CallbackQuery):
            await event.answer(title, show_alert=True)
            if event.message:
                try:
                    await event.message.answer(body, parse_mode="HTML")
                except Exception:
                    pass
            return None
        if isinstance(event, Message):
            await event.answer(body, parse_mode="HTML")
            return None
        return None
