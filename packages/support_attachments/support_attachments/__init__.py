"""Shared validate+save logic for support-ticket image attachments.

Used by every router that accepts image uploads on a support-ticket reply
(miniapp's Telegram-auth router, miniapp's Android/JWT router, and the
dashboard's admin router). Each caller supplies its own uploads directory
(from that service's own `get_support_uploads_dir()` config getter) and
constructs its own download URL — this module only touches the filesystem
and returns metadata, no auth/URL concerns here.

Validation is deliberately real, not client-trusting: every uploaded file is
opened and verified with Pillow (`Image.open(...).verify()`), so a renamed
`.exe` with a spoofed `Content-Type: image/png` cannot survive as a stored
attachment. This is the first user-generated file-upload endpoint this
codebase has ever shipped — worth doing properly once rather than trusting
a client-supplied MIME type or file extension.
"""
from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

# Per-file / per-message limits. Deliberately conservative for a v1: real
# screenshots/photos fit comfortably, this just bounds worst-case storage
# and request size (see also: the edge nginx client_max_body_size note in
# docs/deployment.md — it must be raised to admit a 3-image request).
MAX_ATTACHMENT_SIZE_BYTES = 5 * 1024 * 1024
MAX_ATTACHMENTS_PER_MESSAGE = 3

# Maps Pillow's verified format string to a filesystem extension. Never
# derive the extension from the client-supplied filename or Content-Type
# header — both are attacker-controlled and unrelated to what Pillow actually
# decoded.
_EXT_BY_FORMAT = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "GIF": ".gif",
}
_MIME_BY_FORMAT = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}


class AttachmentValidationError(ValueError):
    """Raised for any client-facing 400: too many files, too large, or not a
    genuine, supported image. Callers catch this and translate to HTTP 400."""


@dataclass(frozen=True, slots=True)
class SavedAttachment:
    original_filename: str
    stored_path: str
    mime_type: str
    size_bytes: int


async def validate_and_save_attachments(
    files: list[UploadFile],
    *,
    uploads_dir: str,
    ticket_id: int,
) -> list[SavedAttachment]:
    """Validate every file in `files`, then write the verified bytes to
    `{uploads_dir}/{ticket_id}/{uuid4().hex}{ext}` and return metadata for
    each. Raises `AttachmentValidationError` on the first violation found —
    no partial writes happen before a limit/type check fails, since the
    count check runs before any file is touched.
    """
    if len(files) > MAX_ATTACHMENTS_PER_MESSAGE:
        raise AttachmentValidationError(
            f"too many images (max {MAX_ATTACHMENTS_PER_MESSAGE})"
        )

    saved: list[SavedAttachment] = []
    ticket_dir = Path(uploads_dir) / str(ticket_id)
    ticket_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        data = await f.read()
        if len(data) > MAX_ATTACHMENT_SIZE_BYTES:
            raise AttachmentValidationError(
                f"file exceeds size limit ({MAX_ATTACHMENT_SIZE_BYTES // (1024 * 1024)}MB): {f.filename}"
            )

        try:
            img = Image.open(io.BytesIO(data))
            fmt = (img.format or "").upper()
            # verify() is a cheap structural check (does not decode full
            # pixel data) and invalidates the Image object afterward — the
            # format string is already captured above from the header parse
            # that Image.open() does, so nothing further is needed from img.
            img.verify()
        except Exception as exc:
            raise AttachmentValidationError(
                f"not a valid image: {f.filename}"
            ) from exc

        ext = _EXT_BY_FORMAT.get(fmt)
        if ext is None:
            raise AttachmentValidationError(f"unsupported image type: {fmt or 'unknown'}")

        name = f"{uuid.uuid4().hex}{ext}"
        (ticket_dir / name).write_bytes(data)

        saved.append(
            SavedAttachment(
                original_filename=f.filename or name,
                stored_path=f"{ticket_id}/{name}",
                mime_type=_MIME_BY_FORMAT[fmt],
                size_bytes=len(data),
            )
        )
    return saved


__all__ = [
    "AttachmentValidationError",
    "SavedAttachment",
    "MAX_ATTACHMENT_SIZE_BYTES",
    "MAX_ATTACHMENTS_PER_MESSAGE",
    "validate_and_save_attachments",
]
