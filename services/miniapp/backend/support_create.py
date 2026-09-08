"""Guided creation with initial photos; old JSON creation remains compatible."""
from fastapi import Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from common_db.models import User, UserSubscription, Transaction, SupportTicket, SupportMessage
from common_db.repo import support as repo
from common_db.support_workflow import metadata, now_iso, record_message
from support_attachments import AttachmentValidationError, validate_and_save_attachments
from .database.session import async_session
from .config import get_support_uploads_dir, get_admin_bot_token, get_admin_id
from .schemas.support import TicketDetail, MessageItem, AttachmentOut

CATEGORIES = {"connection": "Подключение", "speed": "Скорость", "payment": "Оплата", "subscription": "Подписка", "other": "Другое"}


def register_creation(router, authenticate, *, telegram, notify):
    async def get_user(session, identity):
        user = await session.scalar(select(User).where(User.tg_id == identity.tg_id if telegram else User.id == identity.id).with_for_update())
        if not user:
            raise HTTPException(404, "user not found")
        return user

    @router.get("/context")
    async def context(identity=Depends(authenticate)):
        async with async_session() as session:
            user = await get_user(session, identity)
            subscriptions = (await session.scalars(select(UserSubscription).where(UserSubscription.user_id == user.id))).all()
            payments = (await session.scalars(select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.created_at.desc()).limit(20))).all()
            return {"subscriptions": [{"id": s.id, "label": s.label or f"#{s.id}"} for s in subscriptions], "payments": [{"id": p.transaction_id, "label": f"{p.amount} · {p.created_at or ''}"} for p in payments]}

    @router.post("/tickets/create", response_model=TicketDetail, status_code=201)
    async def create(
        category: str = Form("other"), platform: str = Form(""), message: str = Form(""),
        subject: str = Form(""), subscription_id: int | None = Form(None), payment_id: str = Form(""),
        images: list[UploadFile] = File(default=[]), identity=Depends(authenticate),
    ):
        if category not in CATEGORIES or not message.strip() or len(message) > 4000 or len(subject) > 200 or len(platform) > 100:
            raise HTTPException(400, "invalid ticket fields")
        now = now_iso()
        async with async_session() as session:
            user = await get_user(session, identity)
            if await repo.count_open_tickets_for_user(session, user.id) >= 5:
                raise HTTPException(429, "too many open tickets")
            snapshot = {"platform": platform or "—", "language": user.language or "ru"}
            if subscription_id:
                sub = await session.scalar(select(UserSubscription).where(UserSubscription.id == subscription_id, UserSubscription.user_id == user.id))
                if not sub:
                    raise HTTPException(404, "subscription not found")
                snapshot["subscription"] = {"id": sub.id, "label": sub.label or "—", "product": sub.product_key or "—"}
            if payment_id:
                payment = await session.scalar(select(Transaction).where(Transaction.transaction_id == payment_id, Transaction.user_id == user.id))
                if not payment:
                    raise HTTPException(404, "payment not found")
                snapshot["payment"] = {"id": payment.transaction_id, "status": payment.order_status, "amount": payment.amount}
            ticket = SupportTicket(user_id=user.id, username=user.username or user.email, subject=subject.strip() or f"{CATEGORIES[category]}{(' · ' + platform) if platform else ''}", message=message.strip(), status="open", category=category, context=snapshot, created_at=now, updated_at=now)
            session.add(ticket)
            await session.flush()
            try:
                saved = await validate_and_save_attachments(images, uploads_dir=get_support_uploads_dir(), ticket_id=ticket.id)
            except AttachmentValidationError as exc:
                raise HTTPException(400, str(exc)) from exc
            msg = SupportMessage(ticket_id=ticket.id, sender="user", text=message.strip(), created_at=now)
            session.add(msg)
            await session.flush()
            attachments = [await repo.add_attachment(session, message_id=msg.id, original_filename=a.original_filename, stored_path=a.stored_path, mime_type=a.mime_type, size_bytes=a.size_bytes, created_at=now) for a in saved]
            await session.flush()
            record_message(ticket, msg)
            await session.commit()
            prefix = "/support" if telegram else "/android/support"
            result = TicketDetail(**metadata(ticket), id=ticket.id, subject=ticket.subject, status=ticket.status, created_at=now, updated_at=now, messages=[MessageItem(id=msg.id, sender="user", text=msg.text, created_at=now, attachments=[AttachmentOut(id=a.id, filename=a.original_filename, mime_type=a.mime_type, size_bytes=a.size_bytes, url=f"{prefix}/tickets/{ticket.id}/attachments/{a.id}") for a in attachments])])
        # Delivery is bounded and checked; creation stays committed if Telegram is unavailable.
        await notify(result.id, user.username, result.subject)
        return result
