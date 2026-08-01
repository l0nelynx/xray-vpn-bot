"""Backfill numeric Remnawave IDs while the panel still runs v2.8.

The script intentionally does not import the Remnawave SDK. It reads the
legacy ``uuid`` and numeric ``id`` fields directly from ``GET /users``, then
audits the local ownership graph. Dry-run is the default; ``--apply`` writes
all safe changes in one database transaction.

Run from the application container (or with the same ``DATABASE_URL`` and
``CONFIG_PATH`` environment)::

    python scripts/backfill_remnawave_ids.py
    python scripts/backfill_remnawave_ids.py --apply

Do not upgrade the panel to v3 until the final report says ``ready: true``.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from common_db.models import Transaction, User, UserSubscription
from common_db.repo import subscriptions
from common_db.repo.users import PAID_ORDER_STATUSES
from common_db.session import make_async_session

logger = logging.getLogger("backfill_remnawave_ids")


@dataclass(frozen=True)
class PanelIndex:
    total: int
    ids: frozenset[int]
    by_legacy_uuid: dict[str, int]
    duplicate_legacy_uuids: dict[str, tuple[int, ...]]


@dataclass(frozen=True)
class BackfillAction:
    user_id: int
    rw_id: int
    kind: str  # resolve_legacy | attach_existing | sync_primary_projection


@dataclass(frozen=True)
class AuditState:
    report: dict[str, Any]
    actions: tuple[BackfillAction, ...]


def _normalize_uuid(value: object) -> str | None:
    """Return a canonical UUID, ignoring legacy sentinel/corrupt values."""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return str(UUID(raw))
    except (AttributeError, TypeError, ValueError):
        return None


def build_panel_index(items: list[dict[str, Any]]) -> PanelIndex:
    """Build an unambiguous legacy UUID -> numeric ID map."""
    ids: set[int] = set()
    candidates: dict[str, set[int]] = {}
    for item in items:
        raw_id = item.get("id")
        try:
            rw_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        ids.add(rw_id)
        legacy_uuid = _normalize_uuid(item.get("uuid"))
        if legacy_uuid:
            candidates.setdefault(legacy_uuid, set()).add(rw_id)

    duplicates = {
        legacy_uuid: tuple(sorted(values))
        for legacy_uuid, values in candidates.items()
        if len(values) > 1
    }
    mapping = {
        legacy_uuid: next(iter(values))
        for legacy_uuid, values in candidates.items()
        if len(values) == 1
    }
    return PanelIndex(
        total=len(items),
        ids=frozenset(ids),
        by_legacy_uuid=mapping,
        duplicate_legacy_uuids=duplicates,
    )


def _unwrap(payload: object) -> object:
    if isinstance(payload, dict) and "response" in payload:
        return payload["response"]
    return payload


def _api_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/api") else f"{normalized}/api"


def _page(payload: object) -> tuple[list[dict[str, Any]], int | None]:
    data = _unwrap(payload)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)], None
    if not isinstance(data, dict):
        raise RuntimeError("unexpected_remnawave_users_response")
    raw_items = data.get("users") or data.get("root") or []
    if not isinstance(raw_items, list):
        raise RuntimeError("unexpected_remnawave_users_collection")
    raw_total = data.get("total")
    try:
        total = int(raw_total) if raw_total is not None else None
    except (TypeError, ValueError):
        total = None
    return [item for item in raw_items if isinstance(item, dict)], total


async def fetch_panel_users(
    *, base_url: str, token: str, page_size: int, timeout: float
) -> list[dict[str, Any]]:
    """Fetch every v2.8 offset page without relying on SDK DTOs."""
    auth = token if token.startswith("Bearer ") else f"Bearer {token}"
    items: list[dict[str, Any]] = []
    start = 0
    async with httpx.AsyncClient(
        base_url=_api_base_url(base_url),
        headers={"Authorization": auth},
        timeout=timeout,
    ) as client:
        while True:
            response = await client.get(
                "/users", params={"start": start, "size": page_size}
            )
            response.raise_for_status()
            page_items, total = _page(response.json())
            items.extend(page_items)
            start += len(page_items)
            if not page_items:
                break
            if total is not None and start >= total:
                break
            if total is None and len(page_items) < page_size:
                break
            if start > 10_000_000:
                raise RuntimeError("remnawave_users_pagination_limit")
    return items


def _sample(values: list[Any], limit: int = 100) -> list[Any]:
    return values[:limit]


async def audit_database(
    session: AsyncSession,
    panel: PanelIndex,
    primary_projection_repairs: dict[int, int] | None = None,
) -> AuditState:
    requested_repairs = primary_projection_repairs or {}
    users = list((await session.scalars(select(User).order_by(User.id))).all())
    links = list(
        (await session.scalars(select(UserSubscription).order_by(UserSubscription.id))).all()
    )
    now_iso = datetime.now().isoformat(timespec="seconds")
    active_transactions = list(
        (await session.scalars(
            select(Transaction)
            .where(
                Transaction.order_status.in_(PAID_ORDER_STATUSES),
                Transaction.expire_date > now_iso,
            )
            .order_by(Transaction.user_id, Transaction.expire_date)
        )).all()
    )
    active_transactions_by_user: dict[int, list[dict[str, Any]]] = {}
    for transaction in active_transactions:
        active_transactions_by_user.setdefault(int(transaction.user_id), []).append({
            "transaction_id": transaction.transaction_id,
            "order_status": transaction.order_status,
            "delivery_status": transaction.delivery_status,
            "expire_date": transaction.expire_date,
            "target_rw_id": (
                int(transaction.target_rw_id)
                if transaction.target_rw_id is not None
                else None
            ),
        })

    links_by_user: dict[int, list[UserSubscription]] = {}
    primary_by_user: dict[int, UserSubscription] = {}
    owners: dict[int, set[int]] = {}
    for link in links:
        links_by_user.setdefault(int(link.user_id), []).append(link)
        owners.setdefault(int(link.rw_id), set()).add(int(link.user_id))
        if link.is_primary:
            primary_by_user[int(link.user_id)] = link
    for user in users:
        if user.rw_id is not None:
            owners.setdefault(int(user.rw_id), set()).add(int(user.id))

    unresolved: list[int] = []
    ignored_non_uuid_legacy: list[dict[str, Any]] = []
    ignored_missing_legacy_profiles: list[int] = []
    conflicts: list[dict[str, Any]] = []
    actions: list[BackfillAction] = []
    planned: dict[int, int] = {}

    for user in users:
        raw_legacy_uuid = str(user.vless_uuid or "").strip()
        legacy_uuid = _normalize_uuid(user.vless_uuid)
        if user.rw_id is None and raw_legacy_uuid and legacy_uuid is None:
            ignored_non_uuid_legacy.append({
                "user_id": int(user.id),
                "value": raw_legacy_uuid,
            })
        if user.rw_id is None and legacy_uuid:
            rw_id = panel.by_legacy_uuid.get(legacy_uuid)
            if rw_id is None:
                if int(user.id) not in active_transactions_by_user:
                    ignored_missing_legacy_profiles.append(int(user.id))
                    continue
                unresolved.append(int(user.id))
                continue
            claimed_by = sorted(owners.get(rw_id, set()) - {int(user.id)})
            previous = planned.get(rw_id)
            if previous is not None and previous != int(user.id):
                claimed_by.append(previous)
            if claimed_by:
                conflicts.append({
                    "rw_id": rw_id,
                    "candidate_user_id": int(user.id),
                    "owner_user_ids": sorted(set(claimed_by)),
                })
                continue
            planned[rw_id] = int(user.id)
            actions.append(BackfillAction(int(user.id), rw_id, "resolve_legacy"))

        if user.rw_id is not None:
            rw_id = int(user.rw_id)
            user_links = links_by_user.get(int(user.id), [])
            has_projected_link = any(int(link.rw_id) == rw_id for link in user_links)
            primary = primary_by_user.get(int(user.id))
            if not has_projected_link or primary is None:
                claimed_by = sorted(owners.get(rw_id, set()) - {int(user.id)})
                if claimed_by:
                    conflicts.append({
                        "rw_id": rw_id,
                        "candidate_user_id": int(user.id),
                        "owner_user_ids": claimed_by,
                    })
                else:
                    actions.append(BackfillAction(int(user.id), rw_id, "attach_existing"))

    multiple_owners = [
        {"rw_id": rw_id, "user_ids": sorted(user_ids)}
        for rw_id, user_ids in sorted(owners.items())
        if len(user_ids) > 1
    ]
    primary_mismatch_details = [
        {
            "user_id": int(user.id),
            "users_rw_id": int(user.rw_id),
            "primary_rw_id": int(primary_by_user[int(user.id)].rw_id),
        }
        for user in users
        if user.rw_id is not None
        and int(user.id) in primary_by_user
        and int(primary_by_user[int(user.id)].rw_id) != int(user.rw_id)
    ]
    users_by_id = {int(user.id): user for user in users}
    confirmed_primary_repairs: list[dict[str, int]] = []
    invalid_primary_repairs: list[dict[str, Any]] = []
    for user_id, expected_rw_id in sorted(requested_repairs.items()):
        user = users_by_id.get(user_id)
        primary = primary_by_user.get(user_id)
        actual_primary_rw_id = int(primary.rw_id) if primary is not None else None
        if user is None or actual_primary_rw_id != expected_rw_id:
            invalid_primary_repairs.append({
                "user_id": user_id,
                "requested_primary_rw_id": expected_rw_id,
                "actual_primary_rw_id": actual_primary_rw_id,
                "reason": "user_not_found" if user is None else "primary_changed",
            })
            continue
        confirmed_primary_repairs.append({
            "user_id": user_id,
            "primary_rw_id": expected_rw_id,
        })
        if user.rw_id is None or int(user.rw_id) != expected_rw_id:
            actions.append(BackfillAction(
                user_id, expected_rw_id, "sync_primary_projection"
            ))

    confirmed_repair_user_ids = {
        item["user_id"] for item in confirmed_primary_repairs
    }
    panel_missing_ids = sorted(
        rw_id for rw_id in owners if rw_id not in panel.ids
    )
    duplicate_panel_uuids = [
        {"legacy_uuid": key, "rw_ids": list(values)}
        for key, values in sorted(panel.duplicate_legacy_uuids.items())
    ]
    unresolved_active_paid_details = [
        {
            "user_id": user_id,
            "transactions": active_transactions_by_user[user_id],
        }
        for user_id in unresolved
    ]

    blockers = {
        "unresolved_user_ids": unresolved,
        "ownership_conflicts": conflicts,
        "multiple_local_owners": multiple_owners,
        "primary_mismatch_user_ids": [
            item["user_id"]
            for item in primary_mismatch_details
            if item["user_id"] not in confirmed_repair_user_ids
        ],
        "invalid_primary_repair_requests": invalid_primary_repairs,
        "panel_missing_rw_ids": panel_missing_ids,
        "duplicate_panel_uuids": duplicate_panel_uuids,
    }
    blocker_count = sum(len(value) for value in blockers.values())
    report = {
        "ready": blocker_count == 0 and not actions,
        "panel_users": panel.total,
        "panel_users_with_legacy_uuid": len(panel.by_legacy_uuid),
        "local_users": len(users),
        "planned": {
            "resolve_legacy": sum(a.kind == "resolve_legacy" for a in actions),
            "attach_existing": sum(a.kind == "attach_existing" for a in actions),
            "sync_primary_projection": sum(
                a.kind == "sync_primary_projection" for a in actions
            ),
        },
        "policy": {
            "missing_panel_profile": "block_only_with_active_paid_transaction",
            "active_paid_order_statuses": list(PAID_ORDER_STATUSES),
        },
        "ignored_counts": {
            "non_uuid_legacy_values": len(ignored_non_uuid_legacy),
            "missing_panel_profiles_without_active_paid_transaction": len(
                ignored_missing_legacy_profiles
            ),
        },
        "ignored_samples": {
            "non_uuid_legacy_values": _sample(ignored_non_uuid_legacy),
            "missing_panel_profiles_without_active_paid_transaction": _sample(
                ignored_missing_legacy_profiles
            ),
        },
        "unresolved_active_paid_details": _sample(unresolved_active_paid_details),
        "primary_mismatch_details": _sample(primary_mismatch_details),
        "confirmed_primary_projection_repairs": confirmed_primary_repairs,
        "blocker_counts": {name: len(value) for name, value in blockers.items()},
        "blocker_samples": {name: _sample(value) for name, value in blockers.items()},
    }
    return AuditState(report=report, actions=tuple(actions))


async def apply_actions(
    session: AsyncSession, actions: tuple[BackfillAction, ...]
) -> None:
    """Apply a previously clean plan; caller owns the transaction."""
    for action in actions:
        user = await session.get(User, action.user_id)
        if user is None:
            raise RuntimeError(f"user_disappeared:{action.user_id}")
        if action.kind == "resolve_legacy" and user.rw_id is not None:
            if int(user.rw_id) != action.rw_id:
                raise RuntimeError(f"user_changed:{action.user_id}")
            continue

        primary = await subscriptions.get_primary(session, action.user_id)
        if action.kind == "sync_primary_projection":
            if primary is None or int(primary.rw_id) != action.rw_id:
                raise RuntimeError(f"primary_changed:{action.user_id}")
            user.rw_id = action.rw_id
            continue

        await subscriptions.attach(
            session,
            user_id=action.user_id,
            rw_id=action.rw_id,
            source="legacy_uuid_backfill_2_8",
            make_primary=(action.kind == "attach_existing" or primary is None),
        )
        if action.kind == "resolve_legacy" and primary is not None:
            # Keep an already-established primary; the legacy profile remains
            # attached as an additional subscription.
            user.rw_id = int(primary.rw_id)
    await session.flush()


async def run_backfill(
    *,
    panel: PanelIndex,
    session_factory: async_sessionmaker,
    apply: bool,
    primary_projection_repairs: dict[int, int] | None = None,
) -> tuple[int, dict[str, Any]]:
    async with session_factory() as session:
        state = await audit_database(
            session, panel, primary_projection_repairs
        )

    has_blockers = any(state.report["blocker_counts"].values())
    if has_blockers:
        return 2, {"mode": "apply" if apply else "dry-run", **state.report}
    if not apply:
        return 0, {"mode": "dry-run", **state.report}

    async with session_factory() as session:
        # Re-audit under the write transaction so a concurrent ownership
        # change cannot invalidate the earlier dry-run plan.
        fresh = await audit_database(
            session, panel, primary_projection_repairs
        )
        if any(fresh.report["blocker_counts"].values()):
            await session.rollback()
            return 2, {"mode": "apply", **fresh.report}
        await apply_actions(session, fresh.actions)
        await session.commit()

    async with session_factory() as session:
        final = await audit_database(
            session, panel, primary_projection_repairs
        )
    report = {
        "mode": "apply",
        "applied": len(state.actions),
        **final.report,
    }
    return (0 if final.report["ready"] else 2), report


def _config_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    env_path = os.environ.get("CONFIG_PATH")
    if env_path:
        return Path(env_path)
    local = Path("config.yml")
    return local if local.exists() else Path("/app/config.yml")


def load_remnawave_config(path: Path) -> tuple[str, str]:
    data: dict[str, Any] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
            if isinstance(loaded, dict):
                data = loaded
    base_url = (os.environ.get("REMNAWAVE_URL") or data.get("remnawave_url") or "").strip()
    token = (os.environ.get("REMNAWAVE_TOKEN") or data.get("remnawave_token") or "").strip()
    if not base_url or not token:
        raise RuntimeError(
            "remnawave_url/token missing: set REMNAWAVE_URL and "
            "REMNAWAVE_TOKEN or provide CONFIG_PATH"
        )
    return base_url, token


def _primary_repair(value: str) -> tuple[int, int]:
    try:
        raw_user_id, raw_rw_id = value.split(":", 1)
        user_id = int(raw_user_id)
        rw_id = int(raw_rw_id)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            "primary repair must have USER_ID:RW_ID format"
        ) from exc
    if user_id <= 0 or rw_id <= 0:
        raise argparse.ArgumentTypeError("primary repair IDs must be positive")
    return user_id, rw_id


async def _main_async(args: argparse.Namespace) -> int:
    base_url, token = load_remnawave_config(_config_path(args.config))
    panel_users = await fetch_panel_users(
        base_url=base_url,
        token=token,
        page_size=args.page_size,
        timeout=args.timeout,
    )
    panel = build_panel_index(panel_users)
    if not panel.by_legacy_uuid:
        raise RuntimeError(
            "panel returned no legacy user UUIDs; run this script against Remnawave 2.8"
        )

    engine, session_factory = make_async_session(default_sqlite_path="db.sqlite3")
    try:
        code, report = await run_backfill(
            panel=panel,
            session_factory=session_factory,
            apply=args.apply,
            primary_projection_repairs=args.primary_projection_repairs,
        )
    finally:
        await engine.dispose()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit/backfill users.rw_id from a Remnawave 2.8 panel"
    )
    parser.add_argument(
        "--apply", action="store_true", help="commit safe changes (default: dry-run)"
    )
    parser.add_argument(
        "--config", help="config.yml path; defaults to CONFIG_PATH/config.yml"
    )
    parser.add_argument(
        "--repair-primary",
        action="append",
        default=[],
        type=_primary_repair,
        metavar="USER_ID:RW_ID",
        help="confirm primary rw_id and synchronize users.rw_id (repeatable)",
    )
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if not 1 <= args.page_size <= 5000:
        parser.error("--page-size must be between 1 and 5000")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    args.primary_projection_repairs = dict(args.repair_primary)
    if len(args.primary_projection_repairs) != len(args.repair_primary):
        parser.error("each --repair-primary USER_ID may be specified only once")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        return asyncio.run(_main_async(args))
    except Exception as exc:
        logger.error("Backfill failed: %s", exc, exc_info=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
