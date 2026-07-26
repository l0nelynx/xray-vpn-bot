"""Audit/backfill canonical Remnawave numeric ids from legacy user UUIDs.

Dry-run is the default. Run inside the miniapp container (or with the same
CONFIG_PATH/DATABASE_URL environment) so the shared DB and Remnawave client
use production configuration::

    python scripts/backfill_remnawave_ids.py
    python scripts/backfill_remnawave_ids.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select

from common_db.models import User
from common_db.repo import subscriptions
from remnawave_client.api import get_user_from_uuid
from services.miniapp.backend.database.session import async_session

# Importing config registers the lazy Remnawave SDK configuration provider.
from services.miniapp.backend import config as _config  # noqa: F401

logger = logging.getLogger("backfill_remnawave_ids")


async def run(*, apply: bool) -> int:
    async with async_session() as session:
        rows = list(await session.scalars(
            select(User)
            .where(User.rw_id.is_(None), User.vless_uuid.is_not(None))
            .order_by(User.id)
        ))

    resolved: list[tuple[int, int]] = []
    failures: list[int] = []
    seen: dict[int, int] = {}
    duplicates: list[tuple[int, int, int]] = []

    for user in rows:
        rem_user = await get_user_from_uuid(str(user.vless_uuid))
        rw_id = rem_user.get("rw_id") if rem_user else None
        if rw_id is None:
            failures.append(user.id)
            continue
        rw_id = int(rw_id)
        prior = seen.get(rw_id)
        if prior is not None and prior != user.id:
            duplicates.append((rw_id, prior, user.id))
            continue
        seen[rw_id] = user.id
        resolved.append((user.id, rw_id))

    if duplicates:
        for rw_id, first, second in duplicates:
            logger.error(
                "duplicate rw_id=%s resolves from users %s and %s", rw_id, first, second
            )
        logger.error("Audit failed; no rows were written.")
        return 2

    logger.info(
        "Audit: candidates=%s resolved=%s unresolved=%s mode=%s",
        len(rows), len(resolved), len(failures), "apply" if apply else "dry-run",
    )
    if failures:
        logger.warning("Unresolved local user ids: %s", ", ".join(map(str, failures)))

    if not apply:
        return 0

    async with async_session() as session:
        for user_id, rw_id in resolved:
            await subscriptions.attach(
                session,
                user_id=user_id,
                rw_id=rw_id,
                source="legacy_backfill",
                make_primary=True,
            )
        await session.commit()
    logger.info("Backfilled %s users.", len(resolved))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true", help="persist audited ids (default: dry-run)"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
