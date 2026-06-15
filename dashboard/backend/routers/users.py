from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete, exists

from ..auth import get_current_user
from ..database.models import User, Transaction
from ..database.session import async_session

# Shared "paid user" predicate + count helpers — see
# packages/common_db/common_db/repo/users.py. Routes still own their
# sessions; the helpers just centralise the WHERE clause so dashboard
# and app can never disagree on what "paid" means.
from common_db.repo import users as _repo_users

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/count")
async def users_count(_: str = Depends(get_current_user)):
    now = datetime.now()
    async with async_session() as session:
        total = await _repo_users.count_users(session)
        paid = await _repo_users.count_paid_users(session, now=now)
        free = total - paid
        banned = await session.scalar(
            select(func.count()).select_from(User).where(User.is_banned == True)
        ) or 0
    return {"total": total, "paid": paid, "free": free, "banned": banned}


_USER_SORT_COLUMNS = {
    "id": User.id,
    "tg_id": User.tg_id,
    "username": User.username,
    "api_provider": User.api_provider,
}


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("id"),
    order: str = Query("desc"),
    search: str = Query(""),
    filter: str = Query("all"),
    _: str = Depends(get_current_user),
):
    now = datetime.now()
    now_iso = now.isoformat(timespec='seconds')
    async with async_session() as session:
        # The is_paid flag and the paid/free filter both use the canonical
        # predicate from common_db.repo.users (Transaction.order_status
        # IN ('confirmed','delivered') AND expire_date > now).
        has_tx = exists(
            select(Transaction.user_id).where(
                Transaction.user_id == User.id,
                Transaction.order_status.in_(_repo_users.PAID_ORDER_STATUSES),
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

        active_paid_sq = _repo_users.active_paid_user_ids_subquery(now)
        if filter == "paid":
            base = base.where(User.id.in_(active_paid_sq))
        elif filter == "free":
            base = base.where(~User.id.in_(active_paid_sq))
        elif filter == "banned":
            base = base.where(User.is_banned == True)
        elif filter == "vip":
            base = base.where(User.vip == 1)

        count_q = select(func.count()).select_from(base.subquery())
        total = await session.scalar(count_q) or 0

        if sort == "is_paid":
            sort_col = has_tx
        else:
            sort_col = _USER_SORT_COLUMNS.get(sort, User.id)
        base = base.order_by(
            sort_col.asc() if order == "asc" else sort_col.desc()
        )

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
                "vip": bool(user.vip),
            })

    return {"items": users, "total": total, "page": page, "per_page": per_page}


@router.get("/{tg_id}")
async def get_user(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
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
            "vip": bool(user.vip),
            "transactions_count": tx_count,
            "total_spent": float(total_spent),
        }


@router.get("/{tg_id}/transactions")
async def get_user_transactions(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
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
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_banned = True
        await session.commit()
    return {"ok": True, "message": f"User {tg_id} banned"}


@router.post("/{tg_id}/unban")
async def unban_user(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_banned = False
        await session.commit()
    return {"ok": True, "message": f"User {tg_id} unbanned"}


@router.post("/{tg_id}/vip")
async def set_vip(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.vip = 1
        await session.commit()
    return {"ok": True, "message": f"User {tg_id} VIP enabled"}


@router.post("/{tg_id}/unvip")
async def unset_vip(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.vip = 0
        await session.commit()
    return {"ok": True, "message": f"User {tg_id} VIP disabled"}


@router.delete("/{tg_id}")
async def delete_user(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await session.execute(delete(Transaction).where(Transaction.user_id == user.id))
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()
    return {"ok": True, "message": f"User {tg_id} deleted"}
