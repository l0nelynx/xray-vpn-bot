"""Telegram customer interface for the shared support queue."""
from contextlib import ExitStack
from io import BytesIO
from secrets import token_hex

import httpx
from aiohttp import ClientError
from aiogram import BaseMiddleware, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from fastapi import UploadFile

from common_db.repo.users import get_user_by_tg_id
from common_db.support_delivery import send_notification, ticket_keyboard
from common_db.support_workflow import can_reopen
from support_attachments import AttachmentValidationError, MAX_ATTACHMENT_SIZE_BYTES, MAX_ATTACHMENTS_PER_MESSAGE
from app.database.models import async_session
from app.database.requests import set_user
from app.settings import secrets
from . import tickets
from .locale import CATEGORIES, label

router = Router(name="customer_support")
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")


class AccountMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        actor = event.from_user
        lang = "ru" if (actor.language_code or "ru").lower().startswith("ru") else "en"
        async with async_session() as session:
            user = await get_user_by_tg_id(session, actor.id)
        if user is None:
            owner = await set_user(actor.id, actor.username, initial_language=lang)
        else:
            owner = user.id
            lang = user.language if user.language in ("ru", "en") else lang
        return await handler(event, {**data, "owner": owner, "lang": lang})


router.message.middleware(AccountMiddleware())
router.callback_query.middleware(AccountMiddleware())


def keyboard(*buttons):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"st:{action}")] for text, action in buttons
    ])


async def menu(message, lang):
    await message.answer(
        label(lang, "welcome") + "\n\n" + label(lang, "hint"),
        reply_markup=keyboard((label(lang, "new"), "new"), (label(lang, "list"), "list:0")),
    )


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, lang):
    await state.clear()
    await menu(message, lang)


async def notify_operator(ticket_id):
    token = secrets.get("admin_bot_token") or secrets.get("token")
    admin_id = secrets.get("admin_id")
    if token and admin_id:
        async with httpx.AsyncClient(timeout=5) as client:
            await send_notification(client, f"https://api.telegram.org/bot{token}/sendMessage", {
                "chat_id": admin_id, "text": f"🆘 Обращение #{ticket_id}",
                **ticket_keyboard(secrets, ticket_id, admin=True),
            })


async def show_list(message, owner, lang, offset):
    rows, more = await tickets.list_page(owner, offset)
    buttons = [
        (f"#{t.id} · {label(lang, t.status)} · {t.subject[:40]}", f"view:{t.id}")
        for t in rows
    ]
    if more:
        buttons.append((label(lang, "more"), f"list:{offset + len(rows)}"))
    buttons.append((label(lang, "new"), "new"))
    await message.answer(label(lang, "list" if rows else "empty"), reply_markup=keyboard(*buttons))


async def show_thread(message, owner, lang, ticket_id, before=None):
    ticket, messages, more = await tickets.conversation(owner, ticket_id, before)
    await message.answer(f"#{ticket.id} · {ticket.subject}\n{label(lang, ticket.status)}")
    for item in messages:
        buttons = [(f"📎 {label(lang, 'image')} {i}", f"image:{ticket_id}:{a.id}")
                   for i, a in enumerate(item.attachments, start=1)]
        await message.answer(
            f"{label(lang, item.sender)}\n{item.text or '📷'}",
            reply_markup=keyboard(*buttons) if buttons else None, disable_web_page_preview=True,
        )
        if item.sender == "admin":
            await tickets.mark_read(owner, ticket_id, item.id)

    buttons = []
    if more:
        buttons.append((label(lang, "older"), f"view:{ticket_id}:{messages[0].id}"))
    if before:
        buttons.append((label(lang, "latest"), f"view:{ticket_id}"))
    if ticket.status != "closed":
        buttons.extend([(label(lang, "reply"), f"reply:{ticket_id}"), (label(lang, "resolve"), f"resolve:{ticket_id}")])
    elif can_reopen(ticket):
        buttons.append((label(lang, "reopen"), f"reopen:{ticket_id}"))
    buttons.append((label(lang, "list"), "list:0"))
    await message.answer(f"#{ticket_id} · {label(lang, ticket.status)}", reply_markup=keyboard(*buttons))


def draft_keyboard(lang, draft):
    key = draft["key"]
    buttons = [(label(lang, "send"), f"send:{key}")]
    if draft["images"] or draft.get("overflow"):
        buttons.append((label(lang, "reset"), f"reset:{key}"))
    buttons.append((label(lang, "cancel"), f"cancel:{key}"))
    return keyboard(*buttons)


async def begin_draft(message, state, lang, *, category=None, ticket_id=None):
    draft = dict(key=token_hex(5), category=category, ticket_id=ticket_id, text="", images=[])
    await state.set_data(draft)
    prompt = label(lang, "need_reply") if ticket_id else label(lang, "describe") + "\n\n" + label(lang, "hint")
    await message.answer(prompt + "\n\n" + label(lang, "compose"), reply_markup=draft_keyboard(lang, draft))


async def show_draft(message, lang, draft, error=None):
    summary = label(lang, "draft").format(chars=len(draft["text"]), count=len(draft["images"]))
    prompt = label(lang, error) + "\n" if error else ""
    await message.answer(prompt + summary + "\n" + label(lang, "replace"), reply_markup=draft_keyboard(lang, draft))


@router.message()
async def edit_draft(message: Message, state: FSMContext, lang):
    draft = await state.get_data()
    if not draft:
        await menu(message, lang)
        return
    text = (message.text or message.caption or "").strip()
    if len(text) > 4000:
        await show_draft(message, lang, draft, "text_limit")
        return
    file = message.photo[-1] if message.photo else message.document
    if file:
        if len(draft["images"]) >= MAX_ATTACHMENTS_PER_MESSAGE:
            draft["overflow"] = True
            await state.set_data(draft)
            await show_draft(message, lang, draft, "invalid")
            return
        if (file.file_size or 0) > MAX_ATTACHMENT_SIZE_BYTES:
            await show_draft(message, lang, draft, "invalid")
            return
        name = message.document.file_name if message.document else "photo.jpg"
        draft["images"].append((file.file_id, name or "image"))
    elif not message.text:
        await show_draft(message, lang, draft, "invalid")
        return
    if text:
        draft["text"] = text
    await state.set_data(draft)
    await show_draft(message, lang, draft)


class ImageBuffer(BytesIO):
    def write(self, chunk):
        if self.tell() + len(chunk) > MAX_ATTACHMENT_SIZE_BYTES:
            raise AttachmentValidationError("image too large")
        return super().write(chunk)


async def send_draft(message, state, owner, lang, draft):
    if draft.get("overflow"):
        await show_draft(message, lang, draft, "invalid")
        return
    try:
        with ExitStack() as stack:
            uploads = []
            for file_id, name in draft["images"]:
                buf = stack.enter_context(ImageBuffer())
                await message.bot.download(file_id, destination=buf)
                uploads.append(UploadFile(file=buf, filename=name[:255]))
            ticket_id = await tickets.submit(owner, ticket_id=draft["ticket_id"], category=draft["category"],
                                             text=draft["text"], files=uploads, lang=lang)
    except AttachmentValidationError:
        await show_draft(message, lang, draft, "invalid")
        return
    except (TelegramAPIError, ClientError, TimeoutError):
        await show_draft(message, lang, draft, "download")
        return
    await state.clear()
    try:
        await message.answer(label(lang, "sent").format(id=ticket_id), reply_markup=keyboard(
            (label(lang, "view"), f"view:{ticket_id}"), (label(lang, "list"), "list:0"),
        ))
    finally:
        await notify_operator(ticket_id)


@router.callback_query(F.data.startswith("st:"))
async def action(callback: CallbackQuery, state: FSMContext, owner, lang):
    await callback.answer()
    message = callback.message
    _, action, *args = callback.data.split(":")
    try:
        if action == "new":
            await state.clear()
            choices = [(label(lang, k), f"category:{k}") for k in CATEGORIES]
            await message.answer(label(lang, "category"), reply_markup=keyboard(*choices, (label(lang, "list"), "list:0")))
        elif action == "category" and args and args[0] in CATEGORIES:
            await begin_draft(message, state, lang, category=args[0])
        elif action in {"send", "reset", "cancel"}:
            draft = await state.get_data()
            if args != [draft.get("key")]:
                raise tickets.TicketError("stale")
            if action == "send":
                await send_draft(message, state, owner, lang, draft)
            elif action == "reset":
                draft.update(images=[], overflow=False)
                await state.set_data(draft)
                await show_draft(message, lang, draft)
            else:
                await state.clear()
                await menu(message, lang)
        elif args and all(s.isascii() and s.isdigit() and int(s) < 2**63 for s in args):
            ticket_id = int(args[0])
            if action == "list":
                await state.clear()
                await show_list(message, owner, lang, ticket_id)
            elif action == "view":
                await state.clear()
                await show_thread(message, owner, lang, ticket_id, int(args[1]) if len(args) == 2 else None)
            elif action == "image" and len(args) == 2:
                path, name = await tickets.image_file(owner, ticket_id, int(args[1]))
                await message.answer_document(FSInputFile(path, filename=name))
            elif action == "reply":
                async with async_session() as session:
                    ticket = await tickets.owned_ticket(session, owner, ticket_id)
                    if ticket.status == "closed":
                        raise tickets.TicketError("closed")
                await begin_draft(message, state, lang, ticket_id=ticket_id)
            elif action in {"resolve", "reopen"}:
                changed = await tickets.change_status(owner, ticket_id, reopen=action == "reopen")
                if changed and action == "reopen":
                    await notify_operator(ticket_id)
                await show_thread(message, owner, lang, ticket_id)
    except tickets.TicketError as exc:
        await message.answer(label(lang, str(exc)))
