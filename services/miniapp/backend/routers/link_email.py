"""Link the current Telegram MiniApp identity to an existing email account.

Survivor is always the email ``users`` row. If that account already has a
different Telegram bound, the request is rejected with ``telegram_conflict``
and the user is directed to support.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from account_linking import merge_tg_into_email

from ..android import repo, security
from ..android.auth_router import limiter
from ..database.session import async_session
from ..notify_log import esc, notify_log
from ..tg_auth import TgUser, get_tg_user

from common_db.repo import users as _repo_users

router = APIRouter(prefix="/api/link", tags=["link-email"])
logger = logging.getLogger(__name__)


class LinkEmailRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LinkEmailResponse(BaseModel):
    result: str  # ok | already_linked | merged_pro | merged_free
    survivor_id: int


@router.post("/email", response_model=LinkEmailResponse)
@limiter.limit("5/minute")
async def link_email(
    body: LinkEmailRequest,
    request: Request,
    tg: TgUser = Depends(get_tg_user),
) -> LinkEmailResponse:
    email = str(body.email).strip().lower()
    email_user = await repo.find_user_by_email(email)
    if not await security.verify_password(
        email_user.password_hash if email_user else None, body.password
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials"},
        )
    assert email_user is not None

    if email_user.is_banned:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "banned"},
        )

    if email_user.tg_id is not None and int(email_user.tg_id) != int(tg.tg_id):
        await notify_log(
            f"⚠️ <b>MiniApp email link: telegram_conflict</b>\n"
            f"email: <code>{esc(email)}</code> id=<code>{email_user.id}</code>\n"
            f"bound_tg: <code>{email_user.tg_id}</code>\n"
            f"request_tg: <code>{tg.tg_id}</code>"
        )
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "telegram_conflict"},
        )

    if email_user.tg_id is not None and int(email_user.tg_id) == int(tg.tg_id):
        return LinkEmailResponse(result="already_linked", survivor_id=email_user.id)

    async with async_session() as session:
        tg_user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)

        if tg_user is not None and tg_user.id == email_user.id:
            # Same row without tg_id somehow — bind and finish.
            tg_user.tg_id = tg.tg_id
            await session.commit()
            await notify_log(
                f"🔗 <b>MiniApp email link: ok</b>\n"
                f"user: <code>{email_user.id}</code> {esc(email)}\n"
                f"tg: <code>{tg.tg_id}</code>"
            )
            return LinkEmailResponse(result="ok", survivor_id=email_user.id)

        if tg_user is not None and tg_user.email not in (None, ""):
            # Current Telegram row already has its own email credentials.
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"code": "already_has_email"},
            )

        if tg_user is None:
            email_row = await _repo_users.get_user_by_id(session, email_user.id)
            if email_row is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail={"code": "user_not_found"},
                )
            email_row.tg_id = tg.tg_id
            await session.commit()
            await notify_log(
                f"🔗 <b>MiniApp email link: ok</b>\n"
                f"user: <code>{email_user.id}</code> {esc(email)}\n"
                f"tg: <code>{tg.tg_id}</code> (no prior TG row)"
            )
            return LinkEmailResponse(result="ok", survivor_id=email_user.id)

        try:
            merge = await merge_tg_into_email(
                session,
                email_user_id=email_user.id,
                tg_user_id=tg_user.id,
                tg_id=tg.tg_id,
            )
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error("MiniApp email link merge failed: %s", exc, exc_info=True)
            await notify_log(
                f"❌ <b>MiniApp email link: merge_failed</b>\n"
                f"email: <code>{esc(email)}</code> id=<code>{email_user.id}</code>\n"
                f"tg: <code>{tg.tg_id}</code> user=<code>{tg_user.id}</code>\n"
                f"error: <code>{esc(str(exc)[:300])}</code>"
            )
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "merge_failed"},
            ) from exc

    result = merge["result"]
    await notify_log(
        f"🔗 <b>MiniApp email link: {esc(result)}</b>\n"
        f"email survivor: <code>{merge['survivor_id']}</code> {esc(email)}\n"
        f"tg loser: <code>{merge['loser_id']}</code>\n"
        f"tg_id: <code>{tg.tg_id}</code>\n"
        f"tiers: email=<code>{esc(merge['a_tier'])}</code> "
        f"tg=<code>{esc(merge['t_tier'])}</code>"
    )
    return LinkEmailResponse(
        result=result if result in ("ok", "merged_pro", "merged_free") else "ok",
        survivor_id=int(merge["survivor_id"]),
    )
