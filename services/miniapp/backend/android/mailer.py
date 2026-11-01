"""Verification-code templates and the shared SMTP sender."""
from __future__ import annotations

from common_db.mailer import MailerError, send_email as _send_email
from ..config import get_config


async def send_email(*, to: str, subject: str, text: str, html: str | None = None) -> None:
    await _send_email(config=get_config(), to=to, subject=subject, text=text, html=html)


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
