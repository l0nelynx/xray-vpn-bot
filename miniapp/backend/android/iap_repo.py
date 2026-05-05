"""DB access for Google Play IAP flows."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from ..database.session import async_session


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# --- SKU catalog -----------------------------------------------------------


@dataclass
class SkuRow:
    product_id: str
    days: int
    squad_id: str
    external_squad_id: str
    display_name: str | None
    active: bool


async def get_sku(product_id: str) -> SkuRow | None:
    async with async_session() as s:
        row = (await s.execute(
            text(
                "SELECT product_id, days, squad_id, external_squad_id, "
                "display_name, active FROM google_play_skus "
                "WHERE product_id = :p LIMIT 1"
            ),
            {"p": product_id},
        )).first()
    if row is None:
        return None
    return SkuRow(
        product_id=row[0],
        days=int(row[1]),
        squad_id=row[2],
        external_squad_id=row[3],
        display_name=row[4],
        active=bool(row[5]) if row[5] is not None else True,
    )


async def list_active_skus() -> list[SkuRow]:
    async with async_session() as s:
        rows = (await s.execute(
            text(
                "SELECT product_id, days, squad_id, external_squad_id, "
                "display_name, active FROM google_play_skus "
                "WHERE active = 1 ORDER BY days ASC"
            )
        )).all()
    return [
        SkuRow(
            product_id=r[0],
            days=int(r[1]),
            squad_id=r[2],
            external_squad_id=r[3],
            display_name=r[4],
            active=bool(r[5]) if r[5] is not None else True,
        )
        for r in rows
    ]


# --- Purchases -------------------------------------------------------------


@dataclass
class PurchaseRow:
    id: int
    user_id: int
    product_id: str
    purchase_token: str
    order_id: str | None
    expiry_time: str | None
    acknowledged: bool
    state: str | None
    auto_renewing: bool
    linked_purchase_token: str | None
    subscription_id: str | None
    start_time: str | None
    latest_notification_type: int | None


def _row_to_purchase(row) -> PurchaseRow | None:
    if row is None:
        return None
    return PurchaseRow(
        id=row[0],
        user_id=row[1],
        product_id=row[2],
        purchase_token=row[3],
        order_id=row[4],
        expiry_time=row[5],
        acknowledged=bool(row[6]) if row[6] is not None else False,
        state=row[7],
        auto_renewing=bool(row[8]) if row[8] is not None else False,
        linked_purchase_token=row[9],
        subscription_id=row[10],
        start_time=row[11],
        latest_notification_type=row[12],
    )


_PURCHASE_COLS = (
    "id, user_id, product_id, purchase_token, order_id, expiry_time, "
    "acknowledged, state, auto_renewing, linked_purchase_token, "
    "subscription_id, start_time, latest_notification_type"
)


async def find_purchase_by_token(token: str) -> PurchaseRow | None:
    async with async_session() as s:
        row = (await s.execute(
            text(
                f"SELECT {_PURCHASE_COLS} FROM google_play_purchases "
                f"WHERE purchase_token = :t LIMIT 1"
            ),
            {"t": token},
        )).first()
    return _row_to_purchase(row)


async def upsert_purchase(
    *,
    user_id: int,
    product_id: str,
    purchase_token: str,
    order_id: str | None,
    expiry_time: str | None,
    acknowledged: bool,
    state: str | None,
    auto_renewing: bool,
    linked_purchase_token: str | None,
    subscription_id: str | None,
    start_time: str | None,
    raw_payload: dict[str, Any] | None,
) -> PurchaseRow:
    """Insert-or-update a Google Play subscription record by `purchase_token`.

    Idempotent: replaying a verify with the same token doesn't create dupes.
    Owner reassignment is rejected (see router) — this function trusts the
    caller to have validated user_id matches the existing row when present.
    """
    now = _utcnow_iso()
    raw_str = json.dumps(raw_payload) if raw_payload else None
    async with async_session() as s:
        existing = (await s.execute(
            text(f"SELECT {_PURCHASE_COLS} FROM google_play_purchases WHERE purchase_token = :t LIMIT 1"),
            {"t": purchase_token},
        )).first()
        if existing is None:
            await s.execute(
                text(
                    "INSERT INTO google_play_purchases ("
                    "user_id, product_id, purchase_token, order_id, "
                    "expiry_time, acknowledged, state, auto_renewing, "
                    "linked_purchase_token, subscription_id, start_time, "
                    "raw_payload, created_at, updated_at"
                    ") VALUES ("
                    ":uid, :pid, :tok, :oid, :exp, :ack, :st, :ar, "
                    ":lpt, :sid, :start, :raw, :now, :now"
                    ")"
                ),
                {
                    "uid": user_id,
                    "pid": product_id,
                    "tok": purchase_token,
                    "oid": order_id,
                    "exp": expiry_time,
                    "ack": 1 if acknowledged else 0,
                    "st": state,
                    "ar": 1 if auto_renewing else 0,
                    "lpt": linked_purchase_token,
                    "sid": subscription_id,
                    "start": start_time,
                    "raw": raw_str,
                    "now": now,
                },
            )
        else:
            await s.execute(
                text(
                    "UPDATE google_play_purchases SET "
                    "product_id = :pid, order_id = :oid, expiry_time = :exp, "
                    "acknowledged = :ack, state = :st, auto_renewing = :ar, "
                    "linked_purchase_token = :lpt, subscription_id = :sid, "
                    "start_time = :start, raw_payload = :raw, updated_at = :now "
                    "WHERE purchase_token = :tok"
                ),
                {
                    "tok": purchase_token,
                    "pid": product_id,
                    "oid": order_id,
                    "exp": expiry_time,
                    "ack": 1 if acknowledged else 0,
                    "st": state,
                    "ar": 1 if auto_renewing else 0,
                    "lpt": linked_purchase_token,
                    "sid": subscription_id,
                    "start": start_time,
                    "raw": raw_str,
                    "now": now,
                },
            )
        await s.commit()

        row = (await s.execute(
            text(f"SELECT {_PURCHASE_COLS} FROM google_play_purchases WHERE purchase_token = :t LIMIT 1"),
            {"t": purchase_token},
        )).first()
    return _row_to_purchase(row)


async def update_notification_type(token: str, notification_type: int) -> None:
    async with async_session() as s:
        await s.execute(
            text(
                "UPDATE google_play_purchases SET latest_notification_type = :n, "
                "updated_at = :now WHERE purchase_token = :t"
            ),
            {"n": notification_type, "now": _utcnow_iso(), "t": token},
        )
        await s.commit()


async def find_user_active_subscription(user_id: int) -> PurchaseRow | None:
    """Most recent ACTIVE / IN_GRACE_PERIOD subscription for this user.

    Used by /me to surface subscription state when both fiat and IAP exist —
    we prefer the longest-lasting active record.
    """
    async with async_session() as s:
        row = (await s.execute(
            text(
                f"SELECT {_PURCHASE_COLS} FROM google_play_purchases "
                f"WHERE user_id = :u AND state IN ('ACTIVE','IN_GRACE_PERIOD') "
                f"ORDER BY expiry_time DESC LIMIT 1"
            ),
            {"u": user_id},
        )).first()
    return _row_to_purchase(row)
