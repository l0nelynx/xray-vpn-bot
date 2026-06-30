from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func

from ..auth import get_current_user
from ..currency import convert_to_rub, get_rates
from ..database.models import User, Transaction
from ..database.session import async_session

# Canonical "paid" predicate + counts live in common_db.repo.users.
# Use them to keep the overview endpoint aligned with users.py.
from common_db.repo import users as _repo_users

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _period_range(period: str):
    """Return (date_from_iso, date_to_iso) for the given period name."""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "today":
        return today_start.isoformat(timespec="seconds"), now.isoformat(timespec="seconds")
    elif period == "yesterday":
        yd = today_start - timedelta(days=1)
        return yd.isoformat(timespec="seconds"), today_start.isoformat(timespec="seconds")
    elif period == "week":
        wk = today_start - timedelta(days=6)
        return wk.isoformat(timespec="seconds"), now.isoformat(timespec="seconds")
    elif period == "month":
        mo = today_start - timedelta(days=29)
        return mo.isoformat(timespec="seconds"), now.isoformat(timespec="seconds")
    elif period == "6month":
        mo6 = today_start - timedelta(days=179)
        return mo6.isoformat(timespec="seconds"), now.isoformat(timespec="seconds")
    else:
        return None, None


def _fill_daily_gaps(data: dict[str, float], date_from: str | None, date_to: str | None, default=0.0) -> list[tuple[str, float]]:
    """Fill missing dates with default value. Returns sorted list of (date, value)."""
    if not date_from or not date_to:
        # No range — just return sorted existing data
        return sorted(data.items())

    start = datetime.fromisoformat(date_from[:10])
    end = datetime.fromisoformat(date_to[:10])
    result = []
    d = start
    while d <= end:
        key = d.strftime("%Y-%m-%d")
        result.append((key, data.get(key, default)))
        d += timedelta(days=1)
    return result


def _fill_weekly_gaps(data: dict[str, float], date_from: str | None, date_to: str | None, default=0.0) -> list[tuple[str, float]]:
    """Fill missing weeks (Monday-based) with default value."""
    if not date_from or not date_to:
        return sorted(data.items())

    start = datetime.fromisoformat(date_from[:10])
    end = datetime.fromisoformat(date_to[:10])
    # Align start to Monday
    start = start - timedelta(days=start.weekday())
    result = []
    d = start
    while d <= end:
        key = d.strftime("%Y-%m-%d")
        result.append((key, data.get(key, default)))
        d += timedelta(days=7)
    return result


@router.get("/overview")
async def overview(_: str = Depends(get_current_user)):
    now = datetime.now()
    rates = await get_rates()
    async with async_session() as session:
        total_users = await _repo_users.count_users(session)
        paid_users = await _repo_users.count_paid_users(session, now=now)
        free_users = total_users - paid_users
        # Sum per payment_method, then convert each group to RUB before totalling
        # so mixed-currency methods (CRYPTOPAY=USD, TG_STARS=Stars) are comparable.
        method_rows = await session.execute(
            select(
                Transaction.payment_method,
                func.sum(Transaction.amount).label("total"),
            )
            .where(Transaction.order_status.in_(_repo_users.PAID_ORDER_STATUSES))
            .group_by(Transaction.payment_method)
        )
        revenue = sum(
            convert_to_rub(float(r.total or 0), r.payment_method, rates)
            for r in method_rows
        )
        order_count = await session.scalar(
            select(func.count()).select_from(Transaction).where(
                Transaction.order_status.in_(_repo_users.PAID_ORDER_STATUSES)
            )
        ) or 0
        avg_order = round(revenue / order_count, 2) if order_count else 0

    return {
        "total_users": total_users,
        "paid_users": paid_users,
        "free_users": free_users,
        "revenue": float(revenue),
        "avg_order": avg_order,
    }


def _prev_range(date_from: str | None, date_to: str | None):
    """Equal-length window immediately preceding [date_from, date_to)."""
    if not date_from or not date_to:
        return None, None
    f = datetime.fromisoformat(date_from)
    t = datetime.fromisoformat(date_to)
    delta = t - f
    return (f - delta).isoformat(timespec="seconds"), f.isoformat(timespec="seconds")


async def _revenue_in_range(session, rates, date_from, date_to) -> float:
    q = (
        select(Transaction.payment_method, func.sum(Transaction.amount).label("total"))
        .where(
            Transaction.order_status.in_(_repo_users.PAID_ORDER_STATUSES),
            Transaction.amount != None,
        )
        .group_by(Transaction.payment_method)
    )
    if date_from:
        q = q.where(Transaction.created_at >= date_from)
    if date_to:
        q = q.where(Transaction.created_at < date_to)
    rows = await session.execute(q)
    return sum(convert_to_rub(float(r.total or 0), r.payment_method, rates) for r in rows)


async def _orders_in_range(session, date_from, date_to) -> int:
    q = select(func.count()).select_from(Transaction).where(
        Transaction.order_status.in_(_repo_users.PAID_ORDER_STATUSES)
    )
    if date_from:
        q = q.where(Transaction.created_at >= date_from)
    if date_to:
        q = q.where(Transaction.created_at < date_to)
    return await session.scalar(q) or 0


async def _new_users_in_range(session, date_from, date_to) -> int:
    """Count users whose first transaction timestamp falls in the window."""
    sub = (
        select(
            Transaction.user_id,
            func.min(Transaction.created_at).label("fd"),
        )
        .where(Transaction.created_at != None)
        .group_by(Transaction.user_id)
        .subquery()
    )
    q = select(func.count()).select_from(sub)
    if date_from:
        q = q.where(sub.c.fd >= date_from)
    if date_to:
        q = q.where(sub.c.fd < date_to)
    return await session.scalar(q) or 0


@router.get("/summary")
async def summary(period: str = Query("month"), _: str = Depends(get_current_user)):
    """Period-aware KPI bundle: each metric carries its current value and the
    value for the equal-length previous window so the UI can show deltas. Plus
    all-time context (users, active subs, conversion, lifetime revenue)."""
    date_from, date_to = _period_range(period)
    prev_from, prev_to = _prev_range(date_from, date_to)
    now = datetime.now()
    rates = await get_rates()

    async with async_session() as session:
        rev = await _revenue_in_range(session, rates, date_from, date_to)
        rev_prev = await _revenue_in_range(session, rates, prev_from, prev_to)
        orders = await _orders_in_range(session, date_from, date_to)
        orders_prev = await _orders_in_range(session, prev_from, prev_to)
        new_users = await _new_users_in_range(session, date_from, date_to)
        new_users_prev = await _new_users_in_range(session, prev_from, prev_to)

        total_users = await _repo_users.count_users(session)
        active_subs = await _repo_users.count_paid_users(session, now=now)

        method_rows = await session.execute(
            select(Transaction.payment_method, func.sum(Transaction.amount).label("total"))
            .where(Transaction.order_status.in_(_repo_users.PAID_ORDER_STATUSES))
            .group_by(Transaction.payment_method)
        )
        revenue_all = sum(
            convert_to_rub(float(r.total or 0), r.payment_method, rates) for r in method_rows
        )

    avg = round(rev / orders, 2) if orders else 0.0
    avg_prev = round(rev_prev / orders_prev, 2) if orders_prev else 0.0
    conversion = round(active_subs / total_users * 100, 1) if total_users else 0.0

    return {
        "period": period,
        "revenue": {"value": round(rev, 2), "prev": round(rev_prev, 2)},
        "orders": {"value": orders, "prev": orders_prev},
        "new_users": {"value": new_users, "prev": new_users_prev},
        "avg_order": {"value": avg, "prev": avg_prev},
        "totals": {
            "total_users": total_users,
            "active_subs": active_subs,
            "conversion": conversion,
            "revenue_all_time": round(revenue_all, 2),
        },
    }


@router.get("/revenue")
async def revenue(
    period: str = Query("day"),
    _: str = Depends(get_current_user),
):
    """Revenue aggregated by period.

    Periods: today, yesterday, week, month, 6month.
    Groups by day, except 6month which groups by ISO week (Mon-Sun).
    """
    date_from, date_to = _period_range(period)
    rates = await get_rates()

    async with async_session() as session:
        date_expr = func.substr(Transaction.created_at, 1, 10)

        # Group by (day, payment_method) so each currency group can be
        # converted to RUB before being summed into the daily total.
        query = (
            select(
                date_expr.label("date"),
                Transaction.payment_method,
                func.sum(Transaction.amount).label("total"),
            )
            .where(
                Transaction.order_status.in_(_repo_users.PAID_ORDER_STATUSES),
                Transaction.created_at != None,
                Transaction.amount != None,
            )
            .group_by("date", Transaction.payment_method)
            .order_by("date")
        )

        if date_from:
            query = query.where(Transaction.created_at >= date_from)
        if date_to:
            query = query.where(Transaction.created_at <= date_to)

        result = await session.execute(query)
        rows = result.all()

    # Collapse (day, method) rows into per-day RUB totals.
    daily: dict[str, float] = {}
    for row in rows:
        daily[row.date] = daily.get(row.date, 0.0) + convert_to_rub(
            float(row.total or 0), row.payment_method, rates
        )

    if period == "6month":
        # Aggregate daily data into weekly buckets (Monday-based)
        weekly: dict[str, float] = {}
        for date_key, value in daily.items():
            try:
                d = datetime.fromisoformat(date_key)
                monday = d - timedelta(days=d.weekday())
                week_label = monday.strftime("%Y-%m-%d")
                weekly[week_label] = weekly.get(week_label, 0) + value
            except (ValueError, TypeError):
                continue
        filled = _fill_weekly_gaps(weekly, date_from, date_to)
        return [{"date": k, "revenue": round(v, 2)} for k, v in filled]

    filled = _fill_daily_gaps(daily, date_from, date_to)
    return [{"date": k, "revenue": round(v, 2)} for k, v in filled]


@router.get("/user-growth")
async def user_growth(
    period: str = Query("month"),
    _: str = Depends(get_current_user),
):
    """Number of new users per day (by earliest transaction date).

    Periods: today, yesterday, week, month, 6month.
    Groups by day, except 6month which groups by week.
    """
    date_from, date_to = _period_range(period)

    async with async_session() as session:
        # Users who have transactions — by first transaction date
        sub = (
            select(
                Transaction.user_id,
                func.min(func.substr(Transaction.created_at, 1, 10)).label("first_date"),
            )
            .where(Transaction.created_at != None)
            .group_by(Transaction.user_id)
            .subquery()
        )

        query = (
            select(sub.c.first_date.label("date"), func.count().label("count"))
            .group_by(sub.c.first_date)
            .order_by(sub.c.first_date)
        )

        if date_from:
            query = query.where(sub.c.first_date >= date_from[:10])
        if date_to:
            query = query.where(sub.c.first_date <= date_to[:10])

        result = await session.execute(query)
        rows = result.all()

    if period == "6month":
        weekly: dict[str, float] = {}
        for row in rows:
            try:
                d = datetime.fromisoformat(row.date)
                monday = d - timedelta(days=d.weekday())
                week_label = monday.strftime("%Y-%m-%d")
                weekly[week_label] = weekly.get(week_label, 0) + row.count
            except (ValueError, TypeError):
                continue
        filled = _fill_weekly_gaps(weekly, date_from, date_to, default=0)
        return [{"date": k, "count": int(v)} for k, v in filled]

    daily = {row.date: row.count for row in rows}
    filled = _fill_daily_gaps(daily, date_from, date_to, default=0)
    return [{"date": k, "count": int(v)} for k, v in filled]


@router.get("/payment-methods")
async def payment_methods(_: str = Depends(get_current_user)):
    rates = await get_rates()
    async with async_session() as session:
        result = await session.execute(
            select(
                Transaction.payment_method,
                func.count().label("count"),
                func.sum(Transaction.amount).label("total"),
            )
            .where(
                Transaction.order_status.in_(_repo_users.PAID_ORDER_STATUSES),
                Transaction.payment_method != None,
            )
            .group_by(Transaction.payment_method)
        )
        rows = result.all()

    # `total` is normalised to RUB; `total_native` keeps the original amount.
    return [
        {
            "method": row.payment_method,
            "count": row.count,
            "total": round(convert_to_rub(float(row.total or 0), row.payment_method, rates), 2),
            "total_native": float(row.total or 0),
        }
        for row in rows
    ]


@router.get("/order-statuses")
async def order_statuses(_: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(Transaction.order_status, func.count().label("count"))
            .group_by(Transaction.order_status)
        )
        rows = result.all()

    return [{"status": row.order_status, "count": row.count} for row in rows]
