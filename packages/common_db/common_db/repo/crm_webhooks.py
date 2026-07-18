"""CRM Remnawave webhook rules CRUD and cooldown helpers."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CrmWebhookDelivery, CrmWebhookRule


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


async def create_rule(
    session: AsyncSession,
    *,
    name: str,
    scope: str,
    event: str,
    actions: list[dict],
    created_by: str,
    enabled: bool = True,
    cooldown_hours: int | None = None,
) -> CrmWebhookRule:
    now = _now_iso()
    rule = CrmWebhookRule(
        name=name,
        enabled=enabled,
        scope=scope,
        event=event,
        actions_json=json.dumps(actions, ensure_ascii=False),
        cooldown_hours=cooldown_hours,
        created_at=now,
        updated_at=now,
        created_by=created_by,
    )
    session.add(rule)
    await session.flush()
    return rule


async def get_rule(session: AsyncSession, rule_id: int) -> CrmWebhookRule | None:
    return await session.get(CrmWebhookRule, rule_id)


async def list_rules(session: AsyncSession) -> list[CrmWebhookRule]:
    result = await session.scalars(select(CrmWebhookRule).order_by(desc(CrmWebhookRule.id)))
    return list(result)


async def list_enabled_matching(
    session: AsyncSession,
    *,
    scope: str,
    event: str,
) -> list[CrmWebhookRule]:
    result = await session.scalars(
        select(CrmWebhookRule).where(
            CrmWebhookRule.enabled == True,  # noqa: E712
            CrmWebhookRule.scope == scope,
            CrmWebhookRule.event == event,
        )
    )
    return list(result)


async def update_rule(
    session: AsyncSession,
    rule: CrmWebhookRule,
    **fields,
) -> CrmWebhookRule:
    for key, value in fields.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    rule.updated_at = _now_iso()
    await session.flush()
    return rule


async def delete_rule(session: AsyncSession, rule: CrmWebhookRule) -> None:
    await session.delete(rule)
    await session.flush()


async def record_delivery(
    session: AsyncSession,
    *,
    rule_id: int,
    tg_id: int,
) -> CrmWebhookDelivery:
    row = CrmWebhookDelivery(
        rule_id=rule_id,
        tg_id=tg_id,
        sent_at=_now_iso(),
    )
    session.add(row)
    await session.flush()
    return row


async def has_recent_delivery(
    session: AsyncSession,
    *,
    rule_id: int,
    tg_id: int,
    cooldown_hours: int,
) -> bool:
    """True if a delivery for this rule/user exists within ``cooldown_hours``."""
    if cooldown_hours <= 0:
        return False
    since = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=cooldown_hours)
    ).isoformat(timespec="seconds")
    result = await session.scalar(
        select(CrmWebhookDelivery.id).where(
            CrmWebhookDelivery.rule_id == rule_id,
            CrmWebhookDelivery.tg_id == tg_id,
            CrmWebhookDelivery.sent_at >= since,
        ).limit(1)
    )
    return result is not None


def get_actions(rule: CrmWebhookRule) -> list[dict]:
    try:
        data = json.loads(rule.actions_json or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


async def bump_stats(
    session: AsyncSession,
    rule: CrmWebhookRule,
    *,
    webhooks_received: int = 0,
    messages_sent: int = 0,
    messages_failed: int = 0,
) -> None:
    """Atomically bump per-rule counters (in-memory + flush)."""
    if webhooks_received:
        rule.webhooks_received = int(rule.webhooks_received or 0) + webhooks_received
    if messages_sent:
        rule.messages_sent = int(rule.messages_sent or 0) + messages_sent
    if messages_failed:
        rule.messages_failed = int(rule.messages_failed or 0) + messages_failed
    await session.flush()
