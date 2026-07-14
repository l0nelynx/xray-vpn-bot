"""CRM condition types and audience evaluation."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common_db.repo import crm_segments as seg_repo
from remnawave_client.segmentation import PREVIEW_LIMIT

from .crm_model_adapter import (
    CONDITION_SEGMENT,
    CONDITION_TG_ALLOWLIST,
    CONDITION_USER_TYPE,
)
from .crm_service import scan_segment, segment_catalog

CONDITION_CATALOG: list[dict[str, Any]] = [
    {
        "type": CONDITION_SEGMENT,
        "label": "Сегмент",
        "description": "Скан Remnawave + локальная БД",
        "required": True,
        "max_count": 1,
    },
    {
        "type": CONDITION_USER_TYPE,
        "label": "Тип пользователя",
        "description": "Free или Paid/VIP",
        "required": False,
        "fields": [
            {
                "name": "value",
                "label": "Тип",
                "type": "select",
                "options": seg_repo.USER_TYPE_OPTIONS,
                "default": seg_repo.USER_TYPE_ALL,
            }
        ],
    },
    {
        "type": CONDITION_TG_ALLOWLIST,
        "label": "Ручной отбор",
        "description": "Ограничить получателей выбранными tg_id",
        "required": False,
        "fields": [
            {"name": "tg_ids", "label": "TG IDs", "type": "tg_ids"},
        ],
    },
]


def condition_types_catalog() -> list[dict[str, Any]]:
    return list(CONDITION_CATALOG)


def segment_types_catalog() -> list[dict[str, Any]]:
    """Alias: segment definitions used inside segment condition."""
    return segment_catalog()


def _segment_from_conditions(conditions: list[dict]) -> tuple[str | None, dict, str]:
    segment_id: str | None = None
    params: dict = {}
    user_type = seg_repo.USER_TYPE_ALL

    for cond in conditions:
        ctype = cond.get("type")
        if ctype == CONDITION_SEGMENT:
            segment_id = cond.get("segment_id")
            params = dict(cond.get("params") or {})
        elif ctype == CONDITION_USER_TYPE:
            user_type = cond.get("value", seg_repo.USER_TYPE_ALL)

    if "user_type" not in params and user_type != seg_repo.USER_TYPE_ALL:
        params["user_type"] = user_type
    elif CONDITION_USER_TYPE not in [c.get("type") for c in conditions]:
        params.setdefault("user_type", user_type)

    return segment_id, params, user_type


def segment_id_from_conditions(conditions: list[dict]) -> str | None:
    segment_id, _, _ = _segment_from_conditions(conditions)
    return segment_id


def _allowlist_from_conditions(conditions: list[dict]) -> set[int] | None:
    allow: set[int] = set()
    for cond in conditions:
        if cond.get("type") == CONDITION_TG_ALLOWLIST:
            allow.update(int(t) for t in (cond.get("tg_ids") or []))
    return allow if allow else None


async def evaluate_conditions(
    session: AsyncSession,
    rw_client,
    conditions: list[dict],
    *,
    preview_limit: int | None = PREVIEW_LIMIT,
) -> tuple[list[int], list[dict], int, str | None]:
    """Return (tg_ids, preview_users, total, warning). AND semantics."""
    segment_id, params, user_type = _segment_from_conditions(conditions)
    if not segment_id:
        return [], [], 0, None

    allowlist = _allowlist_from_conditions(conditions)

    users, total, warning = await scan_segment(
        session,
        rw_client,
        segment_id,
        days_threshold=int(params.get("days_threshold", 3)),
        traffic_threshold=float(params.get("traffic_threshold", 0.8)),
        invoice_max_age_hours=int(params.get("invoice_max_age_hours", 48)),
        torrent_days=int(params.get("torrent_days", 7)),
        preview_limit=preview_limit,
        user_type=str(params.get("user_type", user_type)),
    )

    tg_ids = [u["tg_id"] for u in users if u.get("tg_id") is not None]

    if allowlist is not None:
        tg_ids = [tg_id for tg_id in tg_ids if tg_id in allowlist]
        users = [u for u in users if u.get("tg_id") in allowlist]
        total = len(tg_ids)

    return tg_ids, users, total, warning


async def evaluate_conditions_full(
    session: AsyncSession,
    rw_client,
    conditions: list[dict],
) -> tuple[list[int], str | None]:
    """Full audience for runner/events (no preview cap)."""
    tg_ids, _, _, warning = await evaluate_conditions(
        session, rw_client, conditions, preview_limit=None
    )
    return tg_ids, warning
