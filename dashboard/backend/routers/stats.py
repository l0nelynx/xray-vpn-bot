from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func

from ..auth import get_current_user
from ..database.models import User, Transaction
from ..database.session import async_session

router = APIRouter(prefix="/api/stats", tags=["stats"])


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
    """Revenue aggregated by period. Period: day, week, month."""
    async with async_session() as session:
        if period == "month":
            date_expr = func.substr(Transaction.created_at, 1, 7)
        elif period == "week":
            # ISO week: truncate to YYYY-MM-DD then group
            date_expr = func.substr(Transaction.created_at, 1, 10)
        else:
            date_expr = func.substr(Transaction.created_at, 1, 10)

        result = await session.execute(
            select(date_expr.label("date"), func.sum(Transaction.amount).label("total"))
            .where(
                Transaction.order_status.in_(["confirmed", "delivered"]),
                Transaction.created_at != None,
                Transaction.amount != None,
            )
            .group_by("date")
            .order_by("date")
        )
        rows = result.all()

    return [{"date": row.date, "revenue": float(row.total or 0)} for row in rows]


@router.get("/user-growth")
async def user_growth(_: str = Depends(get_current_user)):
    """Number of new users per day (by earliest transaction date)."""
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

        result = await session.execute(
            select(sub.c.first_date.label("date"), func.count().label("count"))
            .group_by(sub.c.first_date)
            .order_by(sub.c.first_date)
        )
        rows = result.all()

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
