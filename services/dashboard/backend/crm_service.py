"""CRM scan orchestration — joins local DB users with Remnawave data."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common_db.models import User
from common_db.repo import crm_segments as seg_repo
from remnawave_client.perks import apply_crm_bonus_days, apply_crm_bonus_traffic
from remnawave_client.segmentation import (
    DEFAULT_DAYS_THRESHOLD,
    DEFAULT_INVOICE_MAX_AGE_HOURS,
    DEFAULT_TORRENT_DAYS,
    DEFAULT_TRAFFIC_THRESHOLD,
    PREVIEW_LIMIT,
    SEGMENT_DEVICE_LIMIT,
    SEGMENT_EXPIRED,
    SEGMENT_EXPIRING_SOON,
    SEGMENT_LIMITED,
    SEGMENT_NEVER_CONNECTED,
    SEGMENT_TORRENT,
    SEGMENT_TRAFFIC_LOW,
    SEGMENT_UNPAID_INVOICE,
    matches_rw_segment,
    segment_meta,
)
from remnawave_client.torrent_blocker import collect_torrent_user_uuids

logger = logging.getLogger(__name__)


def _scan_user_row(user: User, meta: dict | None = None) -> dict:
    return {
        "tg_id": user.tg_id,
        "username": user.username,
        "vless_uuid": user.vless_uuid,
        "meta": meta or {},
    }


async def _enrich_device_counts(
    rw_client,
    crm_by_uuid: dict[str, dict],
    uuids: list[str],
) -> None:
    """Fill device_count for users missing it (segment device_limit)."""
    sem = asyncio.Semaphore(20)

    async def _one(uuid: str) -> None:
        async with sem:
            try:
                resp = await rw_client.get_user_hwid_devices(uuid)
                if resp and uuid in crm_by_uuid:
                    count = int(resp.total) if resp.total else len(resp.devices or [])
                    crm_by_uuid[uuid]["device_count"] = count
            except Exception as exc:
                logger.debug("HWID count failed uuid=%s: %s", uuid, exc)

    await asyncio.gather(*[_one(u) for u in uuids], return_exceptions=True)


async def scan_segment(
    session: AsyncSession,
    rw_client,
    segment_id: str,
    *,
    days_threshold: int = DEFAULT_DAYS_THRESHOLD,
    traffic_threshold: float = DEFAULT_TRAFFIC_THRESHOLD,
    invoice_max_age_hours: int = DEFAULT_INVOICE_MAX_AGE_HOURS,
    torrent_days: int = DEFAULT_TORRENT_DAYS,
) -> tuple[list[dict], int, str | None]:
    """Return (preview_users, total_count, warning)."""

    if segment_id == SEGMENT_UNPAID_INVOICE:
        users = await seg_repo.users_with_unpaid_invoices(
            session, max_age_hours=invoice_max_age_hours
        )
        rows = [_scan_user_row(u, {"order_status": "created"}) for u in users]
        return rows[:PREVIEW_LIMIT], len(rows), None

    local_users = await seg_repo.get_remnawave_broadcast_users(session)
    if not local_users:
        return [], 0, None

    by_uuid = {u.vless_uuid: u for u in local_users if u.vless_uuid}
    warning: str | None = None

    torrent_uuids: set[str] | None = None
    if segment_id == SEGMENT_TORRENT:
        torrent_uuids = await collect_torrent_user_uuids(rw_client, days=torrent_days)
        if not torrent_uuids:
            warning = (
                "Torrent-blocker API вернул пустой список — проверьте версию панели "
                "или права API-токена."
            )

    try:
        crm_users = await rw_client.get_all_users_for_crm()
    except Exception as exc:
        logger.error("CRM scan: Remnawave bulk fetch failed: %s", exc)
        return [], 0, f"Не удалось загрузить пользователей Remnawave: {exc}"

    crm_by_uuid = {u["uuid"]: u for u in crm_users if u.get("uuid")}

    if segment_id == SEGMENT_DEVICE_LIMIT:
        missing = [
            uuid
            for uuid, cu in crm_by_uuid.items()
            if uuid in by_uuid and cu.get("device_count") is None
        ]
        if missing:
            await _enrich_device_counts(rw_client, crm_by_uuid, missing)

    matched: list[dict] = []
    for uuid, db_user in by_uuid.items():
        crm_user = crm_by_uuid.get(uuid)
        if not crm_user:
            continue

        if segment_id == SEGMENT_TORRENT:
            if torrent_uuids and uuid in torrent_uuids:
                matched.append(_scan_user_row(db_user, segment_meta(crm_user)))
            continue

        if matches_rw_segment(
            crm_user,
            segment_id,
            days_threshold=days_threshold,
            traffic_threshold=traffic_threshold,
        ):
            matched.append(_scan_user_row(db_user, segment_meta(crm_user)))

    if segment_id == SEGMENT_NEVER_CONNECTED:
        # Warn when panel does not expose firstConnectedAt on any user
        if crm_users and all(u.get("first_connected_at") is None for u in crm_users):
            warning = (
                "Поле firstConnectedAt недоступно в ответе API — все пользователи "
                "могут попасть в сегмент. Обновите панель Remnawave."
            )

    return matched[:PREVIEW_LIMIT], len(matched), warning


async def apply_campaign_perks(
    rw_client,
    user: User,
    crm_user: dict | None,
    *,
    bonus_days: int | None,
    bonus_traffic_gb: int | None,
) -> tuple[bool, str | None]:
    """Apply CRM perks. Returns (success, error_message)."""
    if not user.vless_uuid:
        return False, "no vless_uuid"
    if not crm_user:
        return False, "remnawave user not found"

    username = user.username or f"user_{user.tg_id}"
    had_perk = bool(bonus_days or bonus_traffic_gb)
    if not had_perk:
        return True, None

    ok = True
    errors: list[str] = []

    if bonus_days and bonus_days > 0:
        if not await apply_crm_bonus_days(
            user_uuid=user.vless_uuid,
            username=username,
            bonus_days=bonus_days,
            crm_user=crm_user,
            client=rw_client,
        ):
            ok = False
            errors.append("bonus_days failed")

    if bonus_traffic_gb and bonus_traffic_gb > 0:
        if not await apply_crm_bonus_traffic(
            user_uuid=user.vless_uuid,
            username=username,
            bonus_gb=bonus_traffic_gb,
            crm_user=crm_user,
            client=rw_client,
        ):
            ok = False
            errors.append("bonus_traffic failed")

    return ok, "; ".join(errors) if errors else None


def segment_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": SEGMENT_NEVER_CONNECTED,
            "title": "Не подключались",
            "description": "Пользователи с подпиской, но без firstConnectedAt в Remnawave",
            "params": [],
        },
        {
            "id": SEGMENT_EXPIRED,
            "title": "Expired",
            "description": "Статус подписки expired",
            "params": [],
        },
        {
            "id": SEGMENT_LIMITED,
            "title": "LIMITED",
            "description": "Статус подписки limited (трафик исчерпан)",
            "params": [],
        },
        {
            "id": SEGMENT_TRAFFIC_LOW,
            "title": "Скоро кончится трафик",
            "description": "Использовано ≥ порога от лимита трафика",
            "params": [
                {
                    "name": "traffic_threshold",
                    "label": "Порог использования (0.5–0.95)",
                    "type": "float",
                    "default": DEFAULT_TRAFFIC_THRESHOLD,
                    "min": 0.5,
                    "max": 0.95,
                }
            ],
        },
        {
            "id": SEGMENT_EXPIRING_SOON,
            "title": "Скоро истечёт подписка",
            "description": "Осталось ≤ N дней до expire_at",
            "params": [
                {
                    "name": "days_threshold",
                    "label": "Дней до истечения",
                    "type": "int",
                    "default": DEFAULT_DAYS_THRESHOLD,
                    "min": 1,
                    "max": 30,
                }
            ],
        },
        {
            "id": SEGMENT_UNPAID_INVOICE,
            "title": "Неоплаченный инвойс",
            "description": "Транзакции со статусом created",
            "params": [
                {
                    "name": "invoice_max_age_hours",
                    "label": "Макс. возраст инвойса (часы)",
                    "type": "int",
                    "default": DEFAULT_INVOICE_MAX_AGE_HOURS,
                    "min": 1,
                    "max": 168,
                }
            ],
        },
        {
            "id": SEGMENT_TORRENT,
            "title": "Torrent Reports",
            "description": "Пользователи из отчётов torrent-blocker",
            "params": [
                {
                    "name": "torrent_days",
                    "label": "Период (дней)",
                    "type": "int",
                    "default": DEFAULT_TORRENT_DAYS,
                    "min": 1,
                    "max": 90,
                }
            ],
        },
        {
            "id": SEGMENT_DEVICE_LIMIT,
            "title": "Лимит устройств",
            "description": "Число устройств ≥ hwidDeviceLimit",
            "params": [],
        },
    ]
