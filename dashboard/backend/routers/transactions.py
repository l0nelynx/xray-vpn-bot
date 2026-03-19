from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func

from ..auth import get_current_user
from ..database.models import Transaction, User
from ..database.session import async_session

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("/recent")
async def recent_transactions(
    limit: int = Query(10, ge=1, le=50),
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        result = await session.execute(
            select(Transaction, User.tg_id, User.username.label("user_username"))
            .join(User, User.id == Transaction.user_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
        )
        rows = result.all()
        return [
            {
                "transaction_id": t.transaction_id,
                "username": t.username,
                "user_tg_id": tg_id,
                "payment_method": t.payment_method,
                "amount": t.amount,
                "order_status": t.order_status,
                "days_ordered": t.days_ordered,
                "created_at": t.created_at,
            }
            for t, tg_id, _ in rows
        ]


@router.get("/{transaction_id}")
async def get_transaction(transaction_id: str, _: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(Transaction, User.tg_id)
            .join(User, User.id == Transaction.user_id)
            .where(Transaction.transaction_id == transaction_id)
        )
        row = result.first()
        if not row:
            raise HTTPException(status_code=404, detail="Transaction not found")
        t, tg_id = row
        return {
            "transaction_id": t.transaction_id,
            "vless_uuid": t.vless_uuid,
            "username": t.username,
            "user_tg_id": tg_id,
            "order_status": t.order_status,
            "delivery_status": t.delivery_status,
            "payment_method": t.payment_method,
            "amount": t.amount,
            "created_at": t.created_at,
            "days_ordered": t.days_ordered,
        }


@router.get("")
async def list_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str = Query(""),
    payment_method: str = Query(""),
    date_from: str = Query(""),
    date_to: str = Query(""),
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        base = (
            select(Transaction, User.tg_id)
            .join(User, User.id == Transaction.user_id)
        )

        if status:
            base = base.where(Transaction.order_status == status)
        if payment_method:
            base = base.where(Transaction.payment_method == payment_method)
        if date_from:
            base = base.where(Transaction.created_at >= date_from)
        if date_to:
            base = base.where(Transaction.created_at <= date_to)

        count_q = select(func.count()).select_from(base.subquery())
        total = await session.scalar(count_q) or 0

        offset = (page - 1) * per_page
        result = await session.execute(
            base.order_by(Transaction.created_at.desc()).offset(offset).limit(per_page)
        )
        rows = result.all()

        items = [
            {
                "transaction_id": t.transaction_id,
                "username": t.username,
                "user_tg_id": tg_id,
                "payment_method": t.payment_method,
                "amount": t.amount,
                "order_status": t.order_status,
                "delivery_status": t.delivery_status,
                "days_ordered": t.days_ordered,
                "created_at": t.created_at,
            }
            for t, tg_id in rows
        ]

    return {"items": items, "total": total, "page": page, "per_page": per_page}
