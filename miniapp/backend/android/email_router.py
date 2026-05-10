"""Email-code flows: verify, password-reset, email-change.

All endpoints under <BASE_PATH>/api/android/auth/email and password/reset.

Anti-enumeration:
  * `request`-style endpoints respond 200 OK regardless of whether the email
    exists, so timing/response shape can't be used to enumerate accounts.
  * `confirm`-style endpoints use generic `code_invalid` errors for both
    "no active code" and "wrong code" cases.

Verifying an email also eagerly provisions a FREE Remnawave subscription so
the Android client can immediately fetch a `vless_uuid` from /me.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from ..config import (
    get_email_code_max_attempts,
    get_email_code_ttl_seconds,
)
from ..notify_log import esc, notify_log
from . import deps, mailer, provisioning, repo, security
from .auth_router import limiter
from .schemas import SimpleStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/android/auth", tags=["android-auth-email"])


# --- Schemas ---------------------------------------------------------------


class EmailVerifyConfirmRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=8, max_length=128)


class EmailChangeRequest(BaseModel):
    new_email: EmailStr


class EmailChangeConfirmRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)


# --- Helpers ---------------------------------------------------------------


def _datetime_iso_now_str() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


async def _send_code(
    *,
    user_id: int,
    purpose: str,
    to_email: str,
    payload: str | None,
    template,
) -> None:
    """Generate, persist, and send a code. Old codes for the purpose are
    invalidated atomically so only the freshest code is valid."""
    code = security.new_email_code()
    code_hash = security.hash_email_code(code)
    await repo.invalidate_pending_codes(user_id, purpose)
    await repo.store_verification_code(
        user_id=user_id,
        purpose=purpose,
        code_hash=code_hash,
        payload=payload,
        ttl_seconds=get_email_code_ttl_seconds(),
    )
    rendered = template(code) if payload is None else template(code, payload)
    subject, body = rendered
    try:
        await mailer.send_email(to=to_email, subject=subject, text=body)
    except mailer.MailerError as exc:
        # Log but surface a generic 5xx — codes are still in the DB and the
        # operator can investigate SMTP without the client knowing why.
        logger.error("Failed to send %s email to %s: %s", purpose, to_email, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "email_send_failed"},
        ) from exc


async def _consume_code(
    *,
    user_id: int,
    purpose: str,
    presented_code: str,
) -> repo.VerificationRow:
    """Locate the active code for (user, purpose), check expiry/attempts,
    constant-time compare, and mark used on success. Raises HTTPException on
    any failure with code=`code_invalid` or `code_exhausted` / `code_expired`."""
    row = await repo.find_active_code(user_id, purpose)
    if row is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "code_invalid"})

    if row.expires_at <= _datetime_iso_now_str():
        await repo.mark_code_used(row.id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "code_expired"})

    if row.attempts >= get_email_code_max_attempts():
        await repo.mark_code_used(row.id)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail={"code": "code_exhausted"})

    if not security.constant_time_code_eq(row.code_hash, presented_code):
        attempts = await repo.increment_code_attempts(row.id)
        if attempts >= get_email_code_max_attempts():
            await repo.mark_code_used(row.id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "code_invalid"})

    await repo.mark_code_used(row.id)
    return row


# --- Email verification (initial + resend) ---------------------------------


@router.post("/email/send-code", response_model=SimpleStatus)
@limiter.limit("3/minute")
async def email_send_code(
    request: Request,
    user: repo.UserRow = Depends(deps.get_current_user),
) -> SimpleStatus:
    if user.email_verified_at:
        return SimpleStatus(status="already_verified")
    if not user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "email_missing"})
    await _send_code(
        user_id=user.id,
        purpose=repo.PURPOSE_VERIFY,
        to_email=user.email,
        payload=None,
        template=mailer.render_verify,
    )
    return SimpleStatus()


@router.post("/email/verify", response_model=SimpleStatus)
@limiter.limit("10/minute")
async def email_verify(
    req: EmailVerifyConfirmRequest,
    request: Request,
    user: repo.UserRow = Depends(deps.get_current_user),
) -> SimpleStatus:
    if user.email_verified_at:
        return SimpleStatus(status="already_verified")
    if not user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "email_missing"})

    await _consume_code(
        user_id=user.id,
        purpose=repo.PURPOSE_VERIFY,
        presented_code=req.code,
    )
    await repo.mark_email_verified(user.id)
    await notify_log(
        f"✅ <b>Email verified</b>\n"
        f"ID: <code>{user.id}</code>\n"
        f"email: <code>{esc(user.email)}</code>"
    )

    # Eagerly hand the user a FREE Remnawave subscription. Failures here
    # don't block verification — the client can retry via /me later.
    try:
        await provisioning.ensure_free_subscription(user.id, user.email)
    except Exception as exc:
        logger.warning("Free provisioning for user %s failed: %s", user.id, exc)

    return SimpleStatus()


# --- Password reset --------------------------------------------------------


@router.post("/password/reset-request", response_model=SimpleStatus)
@limiter.limit("3/minute")
async def password_reset_request(
    req: PasswordResetRequest,
    request: Request,
) -> SimpleStatus:
    """Always returns ok to avoid leaking whether the email is registered."""
    user = await repo.find_user_by_email(str(req.email))
    if user is not None and user.password_hash:
        try:
            await _send_code(
                user_id=user.id,
                purpose=repo.PURPOSE_PASSWORD_RESET,
                to_email=user.email or str(req.email),
                payload=None,
                template=mailer.render_password_reset,
            )
        except HTTPException:
            # Swallow SMTP errors so we don't reveal user existence; logged
            # by _send_code already.
            pass
    return SimpleStatus()


@router.post("/password/reset-confirm", response_model=SimpleStatus)
@limiter.limit("10/minute")
async def password_reset_confirm(
    req: PasswordResetConfirmRequest,
    request: Request,
) -> SimpleStatus:
    user = await repo.find_user_by_email(str(req.email))
    if user is None or not user.password_hash:
        # Generic error keeps enumeration shut.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "code_invalid"})

    await _consume_code(
        user_id=user.id,
        purpose=repo.PURPOSE_PASSWORD_RESET,
        presented_code=req.code,
    )
    await repo.set_password(user.id, security.hash_password(req.new_password))
    await repo.revoke_all_user_tokens(user.id)
    return SimpleStatus()


# --- Email change ----------------------------------------------------------


@router.post("/email/change-request", response_model=SimpleStatus)
@limiter.limit("3/minute")
async def email_change_request(
    req: EmailChangeRequest,
    request: Request,
    user: repo.UserRow = Depends(deps.require_verified_email),
) -> SimpleStatus:
    new_email = str(req.new_email).strip().lower()
    if user.email and new_email == user.email.lower():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "email_unchanged"})
    # Reject if another account already owns the address.
    other = await repo.find_user_by_email(new_email)
    if other is not None and other.id != user.id:
        # Same generic "ok" path as reset-request would be ideal, but the
        # client must know it failed before storing the candidate locally.
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "email_taken"})

    code = security.new_email_code()
    code_hash = security.hash_email_code(code)
    await repo.invalidate_pending_codes(user.id, repo.PURPOSE_EMAIL_CHANGE)
    await repo.store_verification_code(
        user_id=user.id,
        purpose=repo.PURPOSE_EMAIL_CHANGE,
        code_hash=code_hash,
        payload=new_email,
        ttl_seconds=get_email_code_ttl_seconds(),
    )
    subject, body = mailer.render_email_change(code, new_email)
    try:
        await mailer.send_email(to=new_email, subject=subject, text=body)
    except mailer.MailerError as exc:
        logger.error("Email change send to %s failed: %s", new_email, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "email_send_failed"},
        ) from exc
    return SimpleStatus()


@router.post("/email/change-confirm", response_model=SimpleStatus)
@limiter.limit("10/minute")
async def email_change_confirm(
    req: EmailChangeConfirmRequest,
    request: Request,
    user: repo.UserRow = Depends(deps.require_verified_email),
) -> SimpleStatus:
    row = await _consume_code(
        user_id=user.id,
        purpose=repo.PURPOSE_EMAIL_CHANGE,
        presented_code=req.code,
    )
    new_email = (row.payload or "").strip().lower()
    if not new_email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "code_invalid"})

    # Last-second collision check: someone may have registered the address
    # in the window between request and confirm.
    other = await repo.find_user_by_email(new_email)
    if other is not None and other.id != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "email_taken"})

    await repo.update_user_email(user.id, new_email)
    await provisioning.rename_remnawave_email(user.id, new_email)
    # Force re-login on every device after an email change.
    await repo.revoke_all_user_tokens(user.id)
    return SimpleStatus()
