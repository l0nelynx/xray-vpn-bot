from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func

from ..auth import get_current_user
from ..database.models import User, Transaction
from ..database.session import async_session

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


@router.get("/overview")
async def overview(_: str = Depends(get_current_user)):
    now_iso = datetime.now().isoformat(timespec='seconds')
    async with async_session() as session:
        total_users = await session.scalar(select(func.count()).select_from(User)) or 0
        paid_users = await session.scalar(
            select(func.count(func.distinct(Transaction.user_id))).select_from(Transaction).where(
                Transaction.order_status.in_(["confirmed", "delivered"]),
                Transaction.expire_date > now_iso,
            )
        ) or 0
        free_users = total_users - paid_users
        revenue = await session.scalar(
            select(func.sum(Transaction.amount)).where(
                Transaction.order_status.in_(["confirmed", "delivered"])
            )
        ) or 0
        order_count = await session.scalar(
            select(func.count()).select_from(Transaction).where(
                Transaction.order_status.in_(["confirmed", "delivered"])
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

    async with async_session() as session:
        if period == "6month":
            # Group by ISO week: use strftime to get year + week number
            # SQLite: compute Monday of the week via julianday trick
            date_expr = func.substr(Transaction.created_at, 1, 10)
        else:
            date_expr = func.substr(Transaction.created_at, 1, 10)

        query = (
            select(date_expr.label("date"), func.sum(Transaction.amount).label("total"))
            .where(
                Transaction.order_status.in_(["confirmed", "delivered"]),
                Transaction.created_at != None,
                Transaction.amount != None,
            )
            .group_by("date")
            .order_by("date")
        )

        if date_from:
            query = query.where(Transaction.created_at >= date_from)
        if date_to:
            query = query.where(Transaction.created_at <= date_to)

        result = await session.execute(query)
        rows = result.all()

    if period == "6month":
        # Aggregate daily data into weekly buckets (Monday-based)
        from collections import OrderedDict
        weekly: OrderedDict[str, float] = OrderedDict()
        for row in rows:
            try:
                d = datetime.fromisoformat(row.date)
                # Monday of that week
                monday = d - timedelta(days=d.weekday())
                week_label = monday.strftime("%Y-%m-%d")
                weekly[week_label] = weekly.get(week_label, 0) + float(row.total or 0)
            except (ValueError, TypeError):
                continue
        return [{"date": k, "revenue": v} for k, v in weekly.items()]

    return [{"date": row.date, "revenue": float(row.total or 0)} for row in rows]


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
        from collections import OrderedDict
        weekly: OrderedDict[str, int] = OrderedDict()
        for row in rows:
            try:
                d = datetime.fromisoformat(row.date)
                monday = d - timedelta(days=d.weekday())
                week_label = monday.strftime("%Y-%m-%d")
                weekly[week_label] = weekly.get(week_label, 0) + row.count
            except (ValueError, TypeError):
                continue
        return [{"date": k, "count": v} for k, v in weekly.items()]

    return [{"date": row.date, "count": row.count} for row in rows]


@router.get("/payment-methods")
async def payment_methods(_: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(
                Transaction.payment_method,
                func.count().label("count"),
                func.sum(Transaction.amount).label("total"),
            )
            .where(
                Transaction.order_status.in_(["confirmed", "delivered"]),
                Transaction.payment_method != None,
            )
            .group_by(Transaction.payment_method)
        )
        rows = result.all()

    return [
        {"method": row.payment_method, "count": row.count, "total": float(row.total or 0)}
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
