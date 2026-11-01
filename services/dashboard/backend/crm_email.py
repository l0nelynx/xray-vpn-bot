"""Branded CRM email rendering and delivery using the verification-code SMTP."""
from __future__ import annotations

import base64
import html
from io import BytesIO

from PIL import Image, ImageOps
from email_validator import EmailNotValidError, validate_email

from common_db.mailer import send_email
from common_db.models import DashboardBrandingAsset

from .config import get_config
from .crm_variables import render_crm_message

LOGO_CID = "crm-brand-logo"


def normalize_webhook_email(value: str | None) -> str | None:
    if not value or "\r" in value or "\n" in value:
        return None
    try:
        address = validate_email(value.strip(), check_deliverability=False, allow_smtputf8=False)
    except EmailNotValidError:
        return None
    return (address.ascii_email or address.normalized).lower()


def email_action_for_user(actions: list[dict], user) -> dict | None:
    for action in actions:
        if action.get("type") != "send_email" or not action.get("enabled", True):
            continue
        if action.get("send_to_email_from_webhook", False):
            continue
        if not user.email or not user.email_verified_at:
            continue
        if action.get("recipients", "without_telegram") == "without_telegram" and user.tg_id:
            continue
        return action
    return None


def has_email_action(actions: list[dict]) -> bool:
    return any(a.get("type") == "send_email" and a.get("enabled", True) for a in actions)


def render_email(
    *, subject: str, text: str, brand_name: str, logo_src: str,
    context: dict[str, str] | None = None,
) -> tuple[str, str, str]:
    # CRM contexts are escaped for Telegram HTML. Email fields are plain text;
    # unescape substitution values once, then escape the complete HTML output.
    ctx = {key: html.unescape(value) for key, value in (context or {}).items()}
    subject = render_crm_message(subject, ctx).strip()
    # Placeholder values must not inject additional MIME headers either.
    subject = " ".join(subject.splitlines())
    body = render_crm_message(text, ctx).strip()
    brand = html.escape(brand_name)
    safe_subject = html.escape(subject)
    paragraphs = "".join(
        '<p style="margin:0 0 20px;">' + html.escape(p).replace("\n", "<br>") + "</p>"
        for p in body.replace("\r\n", "\n").split("\n\n")
    )
    document = f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_subject}</title></head>
<body style="margin:0;padding:0;background:#f4f4f4;color:#171717;font-family:Arial,Helvetica,sans-serif;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f4f4;">
<tr><td align="center" style="padding:32px 12px;">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="width:100%;max-width:600px;background:#fff;border:1px solid #e5e5e5;border-radius:16px;overflow:hidden;">
<tr><td style="height:3px;background:#171717;font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td style="padding:28px 28px 24px;border-bottom:1px solid #e5e5e5;">
<table role="presentation" cellspacing="0" cellpadding="0"><tr>
<td width="48"><img src="{html.escape(logo_src, quote=True)}" width="44" height="44" alt="{brand}" style="display:block;border:0;"></td>
<td style="padding-left:12px;font-size:23px;line-height:30px;font-weight:700;color:#171717;">{brand}</td>
</tr></table></td></tr>
<tr><td style="padding:30px 28px 12px;">
<h1 style="margin:0 0 24px;font-size:26px;line-height:34px;font-weight:700;overflow-wrap:anywhere;">{safe_subject}</h1>
<div style="font-size:16px;line-height:26px;overflow-wrap:anywhere;">{paragraphs}</div>
<p style="margin:32px 0 24px;font-size:15px;line-height:24px;">С заботой о вашем подключении,<br><strong>команда {brand}</strong></p>
</td></tr>
<tr><td style="padding:20px 28px;background:#fafafa;border-top:1px solid #e5e5e5;font-size:12px;line-height:19px;color:#737373;">
Вы получили это письмо, потому что используете {brand}.<br>Это автоматическое уведомление о вашем аккаунте.
</td></tr></table>
</td></tr></table></body></html>'''
    plain = f"{subject}\n\n{body}\n\nС заботой о вашем подключении,\nкоманда {brand_name}"
    return subject, plain, document


async def email_branding(session) -> tuple[str, bytes]:
    # Reuse the cached, validated branding asset; never fetch external URLs per recipient.
    from .routers.branding import DEFAULT_SVG, _render_icon

    config = get_config()
    asset = await session.get(DashboardBrandingAsset, 1)
    logo = _render_icon(
        asset.sha256 if asset else "default-vp",
        asset.content if asset else DEFAULT_SVG,
        asset.mime_type if asset else "image/svg+xml", 128, False,
    )
    if asset is None:
        # The dashboard's generic VP icon is purple. Keep the email fallback
        # neutral while preserving any explicitly configured brand logo.
        with Image.open(BytesIO(logo)) as source:
            neutral = ImageOps.grayscale(source).convert("RGBA")
            neutral.putalpha(source.getchannel("A"))
        output = BytesIO()
        neutral.save(output, format="PNG", optimize=True)
        logo = output.getvalue()
    return str(config.get("branding_name") or "YourVPN"), logo


async def preview_email(session, *, subject: str, text: str, context: dict[str, str]) -> dict:
    brand, logo = await email_branding(session)
    logo_src = "data:image/png;base64," + base64.b64encode(logo).decode("ascii")
    subject, plain, document = render_email(
        subject=subject, text=text, brand_name=brand, logo_src=logo_src,
        context=context,
    )
    return {"subject": subject, "text": plain, "html": document}


async def send_crm_email(session, *, to: str, action: dict, context: dict[str, str]) -> None:
    brand, logo = await email_branding(session)
    subject, plain, document = render_email(
        subject=action["subject"], text=action["text"], brand_name=brand,
        logo_src=f"cid:{LOGO_CID}", context=context,
    )
    await send_email(
        config=get_config(), to=to, subject=subject, text=plain, html=document,
        inline_image=(LOGO_CID, logo),
    )
