"""Reviewed, one-time reconciliation. Never infer prior grants from spending."""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from sqlalchemy import select

from ..models import CreditLedger, Promo, PromoRedemption, Transaction, User
from ..models.referral_recovery import ReferralNotice, ReferralReceipt
from .balance import credit
from .referral_rewards import eligible, lock_rewards, resolve_referral
from .system import get_points_reward_per_30, get_reward_cap_points


async def calculate(session, adjustments=None):
    adjustments = adjustments or {}
    rate = await get_points_reward_per_30(session)
    cap = await get_reward_cap_points(session)
    groups, issues, purchases = {}, [], []
    # Batch the history reads: recovery can cover years of purchases.
    users = (await session.scalars(select(User))).all()
    lookup = {"users": {u.id: u for u in users}, "owners": defaultdict(list),
              "redemptions": defaultdict(list), "promos": {}}
    for user in users:
        lookup["owners"][user.tg_id].append(user)
    for promo in (await session.scalars(select(Promo).where(Promo.promo_type == "referral"))).all():
        lookup["promos"][promo.promo_code] = promo
    for redemption in (await session.scalars(select(PromoRedemption).where(PromoRedemption.promo_type == "referral"))).all():
        lookup["redemptions"][redemption.tg_id].append(redemption)
    ledgers = defaultdict(list)
    for entry in (await session.scalars(select(CreditLedger).order_by(CreditLedger.id))).all():
        ledgers[entry.user_id].append(entry)
    pending_legacy_credits = (await session.scalars(select(Transaction.transaction_id).join(
        ReferralReceipt, ReferralReceipt.transaction_id == Transaction.transaction_id
    ).where(ReferralReceipt.kind == "legacy", Transaction.payment_method == "BONUS_CREDITS",
            Transaction.order_status.in_(["confirmed", "pending"]), Transaction.delivery_status != 1))).all()
    issues.extend({"transaction_id": tx_id, "reason": "legacy_credit_delivery_pending"} for tx_id in pending_legacy_credits)
    transactions = (await session.scalars(select(Transaction).where(
        Transaction.delivery_status == 1,
        Transaction.order_status.in_(["confirmed", "delivered"]),
    ).order_by(Transaction.transaction_id))).all()
    for tx in transactions:
        if not eligible(tx):
            if tx.amount is None and tx.days_ordered > 0:
                try:
                    if await resolve_referral(session, tx, lookup):
                        issues.append({"transaction_id": tx.transaction_id, "reason": "unknown_payment_amount"})
                except ValueError as exc:
                    issues.append({"transaction_id": tx.transaction_id, "reason": str(exc)})
            continue
        try:
            resolved = await resolve_referral(session, tx, lookup)
        except ValueError as exc:
            issues.append({"transaction_id": tx.transaction_id, "reason": str(exc)})
            continue
        if resolved is None:
            continue
        promo, owner = resolved
        group = groups.setdefault(promo.promo_code, {"promo": promo, "owner": owner, "days": 0, "transactions": []})
        group["days"] += tx.days_ordered
        group["transactions"].append(tx.transaction_id)
        purchases.append(tx.transaction_id)

    rows = []
    seen_owners = set()
    for code, group in sorted(groups.items()):
        promo, owner = group["promo"], group["owner"]
        if owner.id in seen_owners:
            issues.append({"transaction_id": code, "reason": "multiple_codes_for_same_owner"})
        seen_owners.add(owner.id)
        ledger = ledgers[owner.id]
        automatic = sum(e.amount for e in ledger if e.source == "promo" and e.reference == f"referral:{code}")
        # Only admin grants can be proposed as manual compensation. The admin
        # reviews this assumption and may enter a smaller amount (including 0).
        admin_grants = sum(e.amount for e in ledger if e.source == "admin" and e.amount > 0)
        spent = -sum(e.amount for e in ledger if e.source == "payment" and e.amount < 0)
        expected = min((group["days"] // 30) * rate, cap)
        paid = max(automatic, promo.points_rewarded)
        before_manual = max(0, expected - paid)
        manual = adjustments.get(str(owner.id), min(admin_grants, before_manual))
        if not isinstance(manual, int) or manual < 0 or manual > before_manual:
            raise ValueError(f"invalid_manual_amount:{owner.id}")
        missing = max(0, before_manual - manual)
        bonus = (missing + 9) // 10
        warnings = []
        if promo.days_purchased > group["days"]:
            warnings.append("Счётчик дней больше восстановленной истории")
        if automatic != promo.points_rewarded:
            warnings.append("Журнал наград и счётчик промокода расходятся; взято большее")
        if ledger and ledger[-1].balance_after != owner.bonus_credits:
            warnings.append("Текущий баланс расходится с последней записью журнала")
        if not ledger and owner.bonus_credits:
            warnings.append("На балансе есть баллы, но журнал начислений отсутствует")
        rows.append({
            "user_id": owner.id, "tg_id": owner.tg_id, "username": owner.username,
            "promo_code": code, "days": group["days"], "counter_days": promo.days_purchased,
            "counter_points": promo.points_rewarded, "transactions": group["transactions"],
            "expected": expected, "automatic": automatic, "paid": paid,
            "admin_grants": admin_grants, "manual": manual, "spent": spent,
            "balance": owner.bonus_credits, "missing": missing, "bonus": bonus,
            "total": missing + bonus, "warnings": warnings,
        })
    if set(adjustments) - {str(r["user_id"]) for r in rows}:
        raise ValueError("unknown_adjustment_user")
    return {
        "rate": rate, "cap": cap, "rows": rows, "issues": issues,
        "purchases_checked": len(purchases),
        "recipients": sum(r["missing"] > 0 for r in rows),
        "missing": sum(r["missing"] for r in rows),
        "bonus": sum(r["bonus"] for r in rows),
        "total": sum(r["total"] for r in rows),
        "manual": sum(r["manual"] for r in rows),
    }


async def preview(session, adjustments=None):
    state = await lock_rewards(session)
    if state.status == "executed":
        raise ValueError("already_executed")
    plan = await calculate(session, adjustments)
    snapshot = {"id": str(uuid.uuid4()), "plan": plan, "adjustments": adjustments or {},
                "created_at": datetime.now(timezone.utc).isoformat()}
    state.snapshot = snapshot
    await session.flush()
    return snapshot


async def execute(session, preview_id):
    state = await lock_rewards(session)
    if state.status == "executed":
        if state.snapshot["id"] != preview_id:
            raise ValueError("already_executed")
        return state.snapshot
    if not state.snapshot or state.snapshot["id"] != preview_id:
        raise ValueError("preview_expired")
    snapshot = state.snapshot
    # Lock wallets before revalidation, so admin credits/spending cannot race
    # with the approved numbers. Use deterministic ordering for all wallets.
    ids = sorted(r["user_id"] for r in snapshot["plan"]["rows"])
    if ids:
        await session.execute(select(User).where(User.id.in_(ids)).order_by(User.id).with_for_update())
    fresh = await calculate(session, snapshot["adjustments"])
    if fresh != snapshot["plan"]:
        raise ValueError("preview_stale")
    if fresh["issues"]:
        raise ValueError("resolve_issues_before_execute")
    for row in fresh["rows"]:
        promo = await session.scalar(select(Promo).where(Promo.promo_code == row["promo_code"]))
        promo.days_purchased = row["days"]
        # Manual compensation is absorbed into the base counter once, so it
        # cannot be awarded again by the next live purchase. Goodwill is extra.
        promo.points_rewarded = max(row["paid"], row["expected"])
        for tx_id in row["transactions"]:
            receipt = await session.get(ReferralReceipt, tx_id)
            if receipt is None:
                session.add(ReferralReceipt(transaction_id=tx_id, kind="reconciled", promo_code=promo.promo_code, points=0))
        if not row["missing"]:
            continue
        await credit(session, row["user_id"], row["missing"], "promo", f"referral:{promo.promo_code}")
        await credit(session, row["user_id"], row["bonus"], "referral_compensation", f"recovery:{snapshot['id']}")
        session.add(ReferralNotice(
            key=f"recovery:{row['user_id']}", user_id=row["user_id"], tg_id=row["tg_id"],
            text=("<b>Мы восстановили ваши реферальные баллы</b>\n\n"
                  "Из-за ошибки часть наград за покупки приглашённых вами пользователей не начислилась вовремя. "
                  "Извините за задержку — мы исправили ошибку.\n\n"
                  f"Начислено за пропущенные награды: <b>{row['missing']}</b> баллов.\n"
                  f"Дополнительно в знак извинения (+10%, с округлением вверх): <b>{row['bonus']}</b> баллов.\n"
                  f"Всего добавлено на баланс: <b>{row['total']}</b> баллов."),
            status="pending" if row["tg_id"] else "unavailable",
        ))
    state.snapshot = {**snapshot, "executed_at": datetime.now(timezone.utc).isoformat()}
    state.status = "executed"
    await session.flush()
    return state.snapshot
