"""SMTP email sender for Android API code flows.

Picks STARTTLS vs implicit TLS based on the configured port (465 = TLS,
587/25 = STARTTLS). Failures raise MailerError so callers can return a
generic 5xx without leaking SMTP internals to the client.
"""
from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from ..config import (
    get_smtp_from,
    get_smtp_host,
    get_smtp_password,
    get_smtp_port,
    get_smtp_use_tls,
    get_smtp_user,
)

logger = logging.getLogger(__name__)


class MailerError(Exception):
    pass


async def send_email(*, to: str, subject: str, text: str, html: str | None = None) -> None:
    host = get_smtp_host()
    if not host:
        raise MailerError("smtp_host not configured")

    sender = get_smtp_from()
    if not sender:
        raise MailerError("smtp_from / smtp_user not configured")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    port = get_smtp_port()
    use_tls = get_smtp_use_tls()
    start_tls = not use_tls and port in (587, 25)
    user = get_smtp_user()
    password = get_smtp_password()

    logger.info(
        "SMTP send: to=%s from=%s host=%s port=%s use_tls=%s start_tls=%s "
        "user=%s password_set=%s subject=%r",
        to, sender, host, port, use_tls, start_tls,
        user or "<empty>", bool(password), subject,
    )

    try:
        await aiosmtplib.send(
            msg,
            hostname=host,
            port=port,
            username=user or None,
            password=password or None,
            use_tls=use_tls,
            start_tls=start_tls,
            timeout=20,
        )
    except aiosmtplib.SMTPResponseException as exc:
        # Сервер ответил числовым кодом — это самый информативный класс
        # ошибок (auth fail / sender rejected / quota / spam policy).
        logger.error(
            "SMTP send to %s failed: %s code=%s message=%r",
            to, type(exc).__name__, exc.code, exc.message,
        )
        raise MailerError(f"{exc.code} {exc.message}") from exc
    except aiosmtplib.SMTPException as exc:
        logger.error(
            "SMTP send to %s failed: %s: %s",
            to, type(exc).__name__, exc, exc_info=True,
        )
        raise MailerError(str(exc) or type(exc).__name__) from exc
    except (OSError, TimeoutError) as exc:
        logger.error(
            "SMTP transport to %s failed: %s: %s (host=%s port=%s)",
            to, type(exc).__name__, exc, host, port, exc_info=True,
        )
        raise MailerError(f"transport: {type(exc).__name__}: {exc}") from exc

    logger.info("SMTP send to %s succeeded", to)


# --- Templates -------------------------------------------------------------
# Short, single-purpose. Codes are 6 digits; embed in plain text only.

def render_verify(code: str) -> tuple[str, str]:
    subject = "Код подтверждения / Verification code"
    body = (
        f"Ваш код подтверждения: {code}\n"
        f"Код действителен 15 минут.\n"
        f"Если вы не запрашивали код, просто проигнорируйте письмо.\n"
        f"\n"
        f"Your verification code: {code}\n"
        f"Valid for 15 minutes. Ignore if you didn't request it.\n"
    )
    return subject, body


def render_password_reset(code: str) -> tuple[str, str]:
    subject = "Сброс пароля / Password reset"
    body = (
        f"Код для сброса пароля: {code}\n"
        f"Код действителен 15 минут. Никому его не сообщайте.\n"
        f"Если вы не запрашивали сброс, проигнорируйте письмо.\n"
        f"\n"
        f"Password reset code: {code}\n"
        f"Valid 15 minutes. Do not share it. Ignore if you didn't request a reset.\n"
    )
    return subject, body


def render_email_change(code: str, new_email: str) -> tuple[str, str]:
    subject = "Подтверждение нового email / Confirm new email"
    body = (
        f"Код для подтверждения нового адреса {new_email}: {code}\n"
        f"Код действителен 15 минут.\n"
        f"\n"
        f"Confirm new address {new_email} with code: {code}\n"
        f"Valid 15 minutes.\n"
    )
    return subject, body
