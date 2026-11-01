"""Shared SMTP transport for verification codes and CRM notifications.

Picks STARTTLS vs implicit TLS based on the configured port (465 = TLS,
587/25 = STARTTLS). Failures raise MailerError so callers can return a
generic 5xx without leaking SMTP internals to the client.
"""
from __future__ import annotations

import logging
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from typing import Any, Mapping

import aiosmtplib

logger = logging.getLogger(__name__)


class MailerError(Exception):
    pass


def _addr_domain(value: str) -> str | None:
    """Достать домен из адреса вида `Name <user@host>` или `user@host`.
    Возвращает host часть или None, если адрес невалидный."""
    _, addr = parseaddr(value)
    if not addr or "@" not in addr:
        return None
    return addr.rsplit("@", 1)[-1].strip().lower() or None


async def send_email(
    *, config: Mapping[str, Any], to: str, subject: str, text: str,
    html: str | None = None, inline_image: tuple[str, bytes] | None = None,
) -> None:
    host = config.get("smtp_host")
    if not host:
        raise MailerError("smtp_host not configured")

    sender = config.get("smtp_from") or config.get("smtp_user")
    if not sender:
        raise MailerError("smtp_from / smtp_user not configured")

    sender_domain = _addr_domain(sender) or "localhost"

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    # SpamAssassin: MISSING_DATE / MISSING_MID. Без Date/Message-ID письмо
    # выглядит как генерируемый ботом спам — добавляем оба заголовка по
    # RFC 5322. make_msgid ставит угловые скобки и FQDN автоматически.
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender_domain)
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
        if inline_image:
            cid, image = inline_image
            msg.get_payload()[-1].add_related(
                image, maintype="image", subtype="png", cid=f"<{cid}>",
                disposition="inline", filename="logo.png",
            )

    port = int(config.get("smtp_port") or 587)
    tls = config.get("smtp_use_tls")
    use_tls = port == 465 if tls is None else bool(tls)
    start_tls = not use_tls and port in (587, 25)
    user = config.get("smtp_user")
    password = config.get("smtp_password")

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
