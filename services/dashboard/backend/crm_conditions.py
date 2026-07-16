"""CRM condition types and audience evaluation."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common_db.repo import crm_segments as seg_repo
from remnawave_client.segmentation import PREVIEW_LIMIT, segment_meta

from .crm_model_adapter import (
    CONDITION_RW_INTERNAL_SQUAD,
    CONDITION_RW_TAG,
    CONDITION_RW_TRAFFIC_LIMIT,
    CONDITION_SEGMENT,
    CONDITION_TG_ALLOWLIST,
    CONDITION_USER_TYPE,
    RW_CONDITION_TYPES,
    normalize_rw_tag,
)
from .crm_service import scan_segment, segment_catalog

logger = logging.getLogger(__name__)

CONDITION_CATALOG: list[dict[str, Any]] = [
    {
        "type": CONDITION_SEGMENT,
        "label": "Segment",
        "category": "base",
        "description": "Scan Remnawave + local DB",
        "required": True,
        "max_count": 1,
    },
    {
        "type": CONDITION_USER_TYPE,
        "label": "User type",
        "category": "base",
        "description": "Free or Paid/VIP",
        "required": False,
        "fields": [
            {
                "name": "value",
                "label": "Type",
                "type": "select",
                "options": seg_repo.USER_TYPE_OPTIONS,
                "default": seg_repo.USER_TYPE_ALL,
            }
        ],
    },
    {
        "type": CONDITION_TG_ALLOWLIST,
        "label": "Manual selection",
        "category": "base",
        "description": "Restrict recipients to the selected tg_ids",
        "required": False,
        "fields": [
            {"name": "tg_ids", "label": "TG IDs", "type": "tg_ids"},
        ],
    },
    {
        "type": CONDITION_RW_INTERNAL_SQUAD,
        "label": "Internal Squad",
        "category": "remnawave",
        "description": "User belongs to the selected internal squad",
        "required": False,
        "fields": [
            {"name": "squad_id", "label": "Squad", "type": "squad_select"},
        ],
    },
    {
        "type": CONDITION_RW_TRAFFIC_LIMIT,
        "label": "Traffic Limit",
        "category": "remnawave",
        "description": "Traffic limit in GB (0 = unlimited)",
        "required": False,
        "fields": [
            {
                "name": "limit_gb",
                "label": "Limit (GB)",
                "type": "int",
                "min": 0,
                "max": 10000,
                "default": 0,
            }
        ],
    },
    {
        "type": CONDITION_RW_TAG,
        "label": "Tag",
        "category": "remnawave",
        "description": "User tag in Remnawave (UPPERCASE, no spaces)",
        "required": False,
        "fields": [
            {"name": "tag", "label": "Tag", "type": "tag", "placeholder": "PROMO_1"},
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


def _rw_conditions_from_list(conditions: list[dict]) -> list[dict]:
    return [c for c in conditions if c.get("type") in RW_CONDITION_TYPES]


def _matches_traffic_limit(crm_user: dict, limit_gb: int) -> bool:
    user_gb = int(crm_user.get("traffic_limit_gb") or 0)
    if limit_gb == 0:
        return int(crm_user.get("traffic_limit_bytes") or 0) == 0
    return user_gb == int(limit_gb)


def _matches_internal_squad(crm_user: dict, squad_id: str) -> bool:
    squads = crm_user.get("active_internal_squad_ids") or []
    return str(squad_id) in {str(s) for s in squads}


async def _apply_rw_filters(
    rw_client,
    users: list[dict],
    rw_conditions: list[dict],
) -> tuple[list[dict], str | None]:
    if not rw_conditions or not users:
        return users, None

    warning: str | None = None
    tag_uuids: set[str] | None = None

    for cond in rw_conditions:
        if cond.get("type") == CONDITION_RW_TAG:
            tag = normalize_rw_tag(cond.get("tag") or "")
            try:
                tagged = await rw_client.get_users_by_tag(tag)
            except Exception as exc:
                logger.error("CRM tag filter failed tag=%s: %s", tag, exc)
                return [], f"Failed to load users by tag {tag}: {exc}"
            tag_uuids = {u["uuid"] for u in tagged if u.get("uuid")}
            if not tag_uuids:
                return [], f"No users found with tag {tag}"

    need_crm_meta = any(
        c.get("type") in (CONDITION_RW_INTERNAL_SQUAD, CONDITION_RW_TRAFFIC_LIMIT)
        for c in rw_conditions
    )

    crm_by_uuid: dict[str, dict] = {}
    if need_crm_meta:
        uuids = {u.get("vless_uuid") for u in users if u.get("vless_uuid")}
        if tag_uuids is not None:
            uuids &= tag_uuids
        if not uuids:
            return [], warning

        try:
            all_crm = await rw_client.get_all_users_for_crm()
        except Exception as exc:
            logger.error("CRM rw filter bulk fetch failed: %s", exc)
            return [], f"Failed to load Remnawave data: {exc}"

        crm_by_uuid = {u["uuid"]: u for u in all_crm if u.get("uuid") in uuids}

    filtered: list[dict] = []
    for row in users:
        uuid = row.get("vless_uuid")
        if not uuid:
            continue
        if tag_uuids is not None and uuid not in tag_uuids:
            continue

        crm_user = crm_by_uuid.get(uuid) if need_crm_meta else None
        if need_crm_meta and not crm_user:
            continue

        ok = True
        for cond in rw_conditions:
            ctype = cond.get("type")
            if ctype == CONDITION_RW_INTERNAL_SQUAD:
                if not crm_user or not _matches_internal_squad(
                    crm_user, str(cond.get("squad_id") or "")
                ):
                    ok = False
                    break
            elif ctype == CONDITION_RW_TRAFFIC_LIMIT:
                if not crm_user or not _matches_traffic_limit(
                    crm_user, int(cond.get("limit_gb", 0))
                ):
                    ok = False
                    break

        if ok:
            meta = dict(row.get("meta") or {})
            if crm_user:
                meta.update(segment_meta(crm_user))
                if crm_user.get("tag"):
                    meta["tag"] = crm_user["tag"]
                if crm_user.get("traffic_limit_gb") is not None:
                    meta["traffic_limit_gb"] = crm_user["traffic_limit_gb"]
                if crm_user.get("active_internal_squad_ids"):
                    meta["squads"] = len(crm_user["active_internal_squad_ids"])
            filtered.append({**row, "meta": meta})

    return filtered, warning


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
    rw_conditions = _rw_conditions_from_list(conditions)

    users, total, warning = await scan_segment(
        session,
        rw_client,
        segment_id,
        days_threshold=int(params.get("days_threshold", 3)),
        traffic_threshold=float(params.get("traffic_threshold", 0.8)),
        invoice_max_age_hours=int(params.get("invoice_max_age_hours", 48)),
        torrent_days=int(params.get("torrent_days", 7)),
        preview_limit=None,
        user_type=str(params.get("user_type", user_type)),
    )

    rw_warning: str | None = None
    if rw_conditions:
        users, rw_warning = await _apply_rw_filters(rw_client, users, rw_conditions)
        total = len(users)
        if rw_warning:
            warning = rw_warning if not warning else f"{warning}; {rw_warning}"

    if allowlist is not None:
        users = [u for u in users if u.get("tg_id") in allowlist]
        total = len(users)

    tg_ids = [u["tg_id"] for u in users if u.get("tg_id") is not None]

    if preview_limit is not None:
        users = users[:preview_limit]

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
