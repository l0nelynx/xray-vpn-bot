"""Build Telegram-sized pages of the public conversation, oldest first."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape

from .locale import label

TEXT_LIMIT = 4096
# Leave room for navigation and ticket actions in the 100-button inline keyboard.
IMAGE_BUTTON_LIMIT = 95


@dataclass
class HistoryPage:
    text: str
    length: int
    images: list = field(default_factory=list)
    image_count: int = 0
    read_cursor: int = 0
    first_message_id: int | None = None


def _timestamp(value):
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return ""
    if date.tzinfo:
        date = date.astimezone(timezone.utc)
    return date.strftime(" · %d.%m.%Y %H:%M UTC")


def history_pages(ticket, messages, lang):
    title = f"🎫 {label(lang, 'ticket')} #{ticket.id} · {ticket.subject}"
    status = label(lang, ticket.status)
    header = f"<b>{escape(title)}</b>\n{escape(status)}"
    header_length = len(title) + 1 + len(status)
    pages = [HistoryPage(header, header_length)]
    image_number = 0

    for item in messages:
        author = ("🎧 " if item.sender == "admin" else "👤 ") + label(lang, item.sender)
        stamp = _timestamp(item.created_at)
        files = []
        for attachment in sorted(item.attachments, key=lambda a: a.id):
            image_number += 1
            files.append((f"📎 {image_number}", f"image:{ticket.id}:{attachment.id}"))
        refs = "  ".join(name for name, _ in files)
        body = item.text or ""
        file_labels = f" · {refs}" if refs else ""
        prefix = f"\n\n<b>{escape(author)}</b><i>{escape(stamp)}</i>{file_labels}\n"
        prefix_length = len(author) + len(stamp) + len(file_labels) + 3
        page = pages[-1]
        if page.first_message_id is not None and (
            page.length + prefix_length + len(body) > TEXT_LIMIT
            or page.image_count + len(files) > IMAGE_BUTTON_LIMIT
        ):
            page = HistoryPage(header, header_length)
            pages.append(page)
        while True:
            room = TEXT_LIMIT - page.length - prefix_length
            # Split the plain text first so an HTML entity can never cross a page boundary.
            cut = room
            if len(body) > room:
                boundary = max(body.rfind("\n", 0, room), body.rfind(" ", 0, room))
                if boundary >= room // 2:
                    cut = boundary + 1
            part, body = body[:cut], body[cut:]
            page.first_message_id = page.first_message_id or item.id
            page.text += prefix + escape(part, quote=False)
            page.length += prefix_length + len(part)
            if files:
                page.images.append(files)
                page.image_count += len(files)
            if not body:
                break
            page = HistoryPage(header, header_length)
            pages.append(page)
        if item.sender == "admin":
            page.read_cursor = max(page.read_cursor, item.id)
    return pages
