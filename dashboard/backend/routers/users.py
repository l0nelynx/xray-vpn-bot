from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete, exists

from ..auth import get_current_user
from ..database.models import User, Transaction
from ..database.session import async_session

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/count")
async def users_count(_: str = Depends(get_current_user)):
    now_iso = datetime.now().isoformat(timespec='seconds')
    async with async_session() as session:
        total = await session.scalar(select(func.count()).select_from(User)) or 0
        paid = await session.scalar(
            select(func.count(func.distinct(Transaction.user_id))).select_from(Transaction).where(
                Transaction.order_status.in_(["confirmed", "delivered"]),
                Transaction.expire_date > now_iso,
            )
        ) or 0
        free = total - paid
        banned = await session.scalar(
            select(func.count()).select_from(User).where(User.is_banned == True)
        ) or 0
    return {"total": total, "paid": paid, "free": free, "banned": banned}


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("id"),
    search: str = Query(""),
    filter: str = Query("all"),
    _: str = Depends(get_current_user),
):
    now_iso = datetime.now().isoformat(timespec='seconds')
    async with async_session() as session:
        has_tx = exists(
            select(Transaction.user_id).where(
                Transaction.user_id == User.id,
                Transaction.order_status.in_(["confirmed", "delivered"]),
                Transaction.expire_date > now_iso,
            )
        ).correlate(User).label("is_paid")

        base = select(User, has_tx)

        if search:
            if search.isdigit():
                base = base.where(
                    (User.username.ilike(f"%{search}%")) | (User.tg_id == int(search))
                )
            else:
                base = base.where(User.username.ilike(f"%{search}%"))

        active_paid_sq = select(Transaction.user_id).where(
            Transaction.order_status.in_(["confirmed", "delivered"]),
            Transaction.expire_date > now_iso,
        ).distinct()
        if filter == "paid":
            base = base.where(User.id.in_(active_paid_sq))
        elif filter == "free":
            base = base.where(~User.id.in_(active_paid_sq))
        elif filter == "banned":
            base = base.where(User.is_banned == True)

        count_q = select(func.count()).select_from(base.subquery())
        total = await session.scalar(count_q) or 0

        if sort == "username":
            base = base.order_by(User.username.asc())
        else:
            base = base.order_by(User.id.desc())

        offset = (page - 1) * per_page
        result = await session.execute(base.offset(offset).limit(per_page))
        rows = result.all()

        users = []
        for user, is_paid in rows:
            users.append({
                "id": user.id,
                "tg_id": user.tg_id,
                "username": user.username,
                "api_provider": user.api_provider,
                "is_banned": bool(user.is_banned),
                "is_paid": bool(is_paid),
                "email": user.email,
                "language": user.language,
            })

    return {"items": users, "total": total, "page": page, "per_page": per_page}


@router.get("/{tg_id}")
async def get_user(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        tx_count = await session.scalar(
            select(func.count()).select_from(Transaction).where(Transaction.user_id == user.id)
        ) or 0
        total_spent = await session.scalar(
            select(func.sum(Transaction.amount)).where(Transaction.user_id == user.id)
        ) or 0

        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "username": user.username,
            "vless_uuid": user.vless_uuid,
            "api_provider": user.api_provider,
            "email": user.email,
            "is_banned": bool(user.is_banned),
            "language": user.language,
            "transactions_count": tx_count,
            "total_spent": float(total_spent),
        }


@router.get("/{tg_id}/transactions")
async def get_user_transactions(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        result = await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc())
        )
        transactions = result.scalars().all()

        return [
            {
                "transaction_id": t.transaction_id,
                "payment_method": t.payment_method,
                "amount": t.amount,
                "created_at": t.created_at,
                "order_status": t.order_status,
                "delivery_status": t.delivery_status,
                "days_ordered": t.days_ordered,
                "expire_date": t.expire_date,
            }
            for t in transactions
        ]


@router.post("/{tg_id}/ban")
async def ban_user(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_banned = True
        await session.commit()
    return {"ok": True, "message": f"User {tg_id} banned"}


@router.post("/{tg_id}/unban")
async def unban_user(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_banned = False
        await session.commit()
    return {"ok": True, "message": f"User {tg_id} unbanned"}


@router.delete("/{tg_id}")
async def delete_user(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await session.execute(delete(Transaction).where(Transaction.user_id == user.id))
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()
    return {"ok": True, "message": f"User {tg_id} deleted"}
