"""Telegram customer interface for the shared support queue."""
from contextlib import ExitStack
from html import escape
from io import BytesIO
from secrets import token_hex

import httpx
from aiohttp import ClientError
from aiogram import BaseMiddleware, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
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
from .history import history_pages

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


def keyboard(*rows):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"st:{action}") for text, action in row]
        for row in rows
    ])


async def screen(message, text, markup, *, edit=False):
    options = dict(reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
    if edit:
        try:
            return await message.edit_text(text, **options)
        except TelegramBadRequest as exc:
            reason = exc.message.lower()
            if "message is not modified" in reason:
                return
            if "message can't be edited" not in reason and "message to edit not found" not in reason:
                raise
    return await message.answer(text, **options)


async def purchase_tip(owner, lang):
    if not await tickets.needs_purchase_tip(owner):
        return ""
    return f"\n\n<blockquote>💡 <b>{label(lang, 'tip_title')}</b>\n{label(lang, 'hint')}</blockquote>"


async def menu(message, owner, lang, *, edit=False):
    brand = escape(str(secrets.get("branding_name") or "VPN"))
    welcome = label(lang, "welcome").format(brand=brand)
    await screen(message, welcome + await purchase_tip(owner, lang), keyboard(
        [(label(lang, "new"), "new")], [(label(lang, "list"), "list:0")],
    ), edit=edit)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, owner, lang):
    await state.clear()
    await menu(message, owner, lang)


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
    buttons = [[(f"#{t.id} · {t.subject[:40]} · {label(lang, t.status)}", f"view:{t.id}")] for t in rows]
    navigation = []
    if offset:
        navigation.append((f"‹ {label(lang, 'back')}", f"list:{max(0, offset - 8)}"))
    if more:
        navigation.append((f"{label(lang, 'next')} ›", f"list:{offset + len(rows)}"))
    if navigation:
        buttons.append(navigation)
    buttons.append([(label(lang, "new"), "new")])
    text = f"<b>{label(lang, 'list')}</b>\n\n" + label(lang, "choose_ticket" if rows else "empty")
    await screen(message, text, keyboard(*buttons), edit=True)


async def show_thread(message, owner, lang, ticket_id, page_index=None, *, before=None):
    ticket, messages = await tickets.conversation(owner, ticket_id)
    pages = history_pages(ticket, messages, lang)
    if before is not None:
        # Buttons on cards sent before pagination used an exclusive message ID.
        eligible = [i for i, page in enumerate(pages) if (page.first_message_id or 0) < before]
        page_index = eligible[-1] if eligible else 0
    index = len(pages) - 1 if page_index is None else min(page_index, len(pages) - 1)
    page = pages[index]
    buttons = list(page.images)
    navigation = []
    if index:
        navigation.append((f"‹ {label(lang, 'older')} · {index}/{len(pages)}", f"page:{ticket_id}:{index - 1}"))
    if index + 1 < len(pages):
        navigation.append((f"{label(lang, 'newer')} · {index + 2}/{len(pages)} ›", f"page:{ticket_id}:{index + 1}"))
    if navigation:
        buttons.append(navigation)
    if ticket.status != "closed":
        buttons.append([(label(lang, "reply"), f"reply:{ticket_id}"), (label(lang, "resolve"), f"resolve:{ticket_id}")])
    elif can_reopen(ticket):
        buttons.append([(label(lang, "reopen"), f"reopen:{ticket_id}")])
    buttons.append([(label(lang, "list"), "list:0")])
    await screen(message, page.text, keyboard(*buttons), edit=True)
    if page.read_cursor:
        await tickets.mark_read(owner, ticket_id, page.read_cursor)


def draft_keyboard(lang, draft):
    key = draft["key"]
    rows = [[(label(lang, "send"), f"send:{key}"), (label(lang, "cancel"), f"cancel:{key}")]]
    if draft["images"] or draft.get("overflow"):
        rows.append([(label(lang, "reset"), f"reset:{key}")])
    return keyboard(*rows)


async def begin_draft(message, state, owner, lang, *, category=None, ticket_id=None):
    draft = dict(key=token_hex(5), category=category, ticket_id=ticket_id, text="", images=[])
    await state.set_data(draft)
    if ticket_id:
        prompt = f"<b>{label(lang, 'reply')} · #{ticket_id}</b>\n\n{label(lang, 'need_reply')}"
    else:
        prompt = f"<b>{label(lang, 'new')} · {label(lang, category)}</b>\n\n{label(lang, 'describe')}"
        prompt += await purchase_tip(owner, lang)
    await screen(message, prompt + "\n\n" + label(lang, "compose"), draft_keyboard(lang, draft), edit=True)


async def show_draft(message, lang, draft, error=None):
    summary = label(lang, "draft").format(chars=len(draft["text"]), count=len(draft["images"]))
    prompt = label(lang, error) + "\n" if error else ""
    await screen(message, prompt + f"<b>{summary}</b>\n" + label(lang, "replace"), draft_keyboard(lang, draft))


@router.message()
async def edit_draft(message: Message, state: FSMContext, owner, lang):
    draft = await state.get_data()
    if not draft:
        await menu(message, owner, lang)
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
        await screen(message, label(lang, "sent").format(id=ticket_id), keyboard(
            [(label(lang, "view"), f"view:{ticket_id}")], [(label(lang, "list"), "list:0")],
        ), edit=True)
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
            rows = [choices[i:i + 2] for i in range(0, len(choices), 2)]
            await screen(message, label(lang, "category"), keyboard(*rows, [(label(lang, "list"), "list:0")]), edit=True)
        elif action == "category" and args and args[0] in CATEGORIES:
            await begin_draft(message, state, owner, lang, category=args[0])
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
                await menu(message, owner, lang, edit=True)
        elif args and all(s.isascii() and s.isdigit() and int(s) < 2**63 for s in args):
            ticket_id = int(args[0])
            if action == "list":
                await state.clear()
                await show_list(message, owner, lang, ticket_id)
            elif action == "view":
                await state.clear()
                await show_thread(message, owner, lang, ticket_id, before=int(args[1]) if len(args) == 2 else None)
            elif action == "page" and len(args) == 2:
                await show_thread(message, owner, lang, ticket_id, int(args[1]))
            elif action == "image" and len(args) == 2:
                path, name = await tickets.image_file(owner, ticket_id, int(args[1]))
                await message.answer_document(FSInputFile(path, filename=name))
            elif action == "reply":
                async with async_session() as session:
                    ticket = await tickets.owned_ticket(session, owner, ticket_id)
                    if ticket.status == "closed":
                        raise tickets.TicketError("closed")
                await begin_draft(message, state, owner, lang, ticket_id=ticket_id)
            elif action in {"resolve", "reopen"}:
                changed = await tickets.change_status(owner, ticket_id, reopen=action == "reopen")
                if changed and action == "reopen":
                    await notify_operator(ticket_id)
                await show_thread(message, owner, lang, ticket_id)
    except tickets.TicketError as exc:
        await message.answer(label(lang, str(exc)))
