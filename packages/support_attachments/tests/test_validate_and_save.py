"""Tests for validate_and_save_attachments — the one file-upload validation
path this codebase has. Covers the security-relevant property directly:
Pillow's real verify() must reject a disguised non-image even when the
client spoofs Content-Type and a plausible filename, not just trust the
client-supplied metadata.
"""
from __future__ import annotations

import io
import os

import pytest
from fastapi import UploadFile
from PIL import Image

from support_attachments import (
    MAX_ATTACHMENT_SIZE_BYTES,
    AttachmentValidationError,
    validate_and_save_attachments,
)


def _upload(data: bytes, filename: str, content_type: str = "image/png") -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(data), headers={"content-type": content_type})


def _png_bytes(size=(10, 10), color="red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="blue").save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.anyio
async def test_genuine_images_are_saved_with_correct_metadata(tmp_path) -> None:
    png, jpg = _png_bytes(), _jpeg_bytes()
    saved = await validate_and_save_attachments(
        [_upload(png, "a.png"), _upload(jpg, "b.jpg", "image/jpeg")],
        uploads_dir=str(tmp_path),
        ticket_id=42,
    )
    assert len(saved) == 2
    assert saved[0].mime_type == "image/png"
    assert saved[1].mime_type == "image/jpeg"
    assert saved[0].original_filename == "a.png"
    assert saved[0].stored_path.startswith("42/")

    full_path = tmp_path / saved[0].stored_path
    assert full_path.is_file()
    assert full_path.read_bytes() == png


@pytest.mark.anyio
async def test_too_many_files_rejected_before_any_write(tmp_path) -> None:
    png = _png_bytes()
    with pytest.raises(AttachmentValidationError, match="too many images"):
        await validate_and_save_attachments(
            [_upload(png, f"{i}.png") for i in range(4)],
            uploads_dir=str(tmp_path),
            ticket_id=99,
        )
    # The count check runs before any file touches disk.
    assert not (tmp_path / "99").exists() or os.listdir(tmp_path / "99") == []


@pytest.mark.anyio
async def test_oversized_file_rejected(tmp_path) -> None:
    big = b"\x89PNG" + os.urandom(MAX_ATTACHMENT_SIZE_BYTES + 1)
    with pytest.raises(AttachmentValidationError, match="exceeds size limit"):
        await validate_and_save_attachments(
            [_upload(big, "big.png")], uploads_dir=str(tmp_path), ticket_id=7
        )


@pytest.mark.anyio
async def test_disguised_non_image_rejected_despite_spoofed_content_type(tmp_path) -> None:
    """The core security property: a non-image with a fake .png filename and
    a spoofed image/png Content-Type must still be rejected, because Pillow
    actually opens and verifies the bytes rather than trusting the client."""
    fake = b"#!/bin/sh\nrm -rf /\n"
    with pytest.raises(AttachmentValidationError, match="not a valid image"):
        await validate_and_save_attachments(
            [_upload(fake, "totally_a_photo.png", "image/png")],
            uploads_dir=str(tmp_path),
            ticket_id=7,
        )
    assert not (tmp_path / "7").exists() or os.listdir(tmp_path / "7") == []


@pytest.mark.anyio
async def test_unsupported_but_genuine_image_format_rejected(tmp_path) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (5, 5)).save(buf, format="BMP")
    with pytest.raises(AttachmentValidationError, match="unsupported image type"):
        await validate_and_save_attachments(
            [_upload(buf.getvalue(), "pic.bmp", "image/bmp")],
            uploads_dir=str(tmp_path),
            ticket_id=7,
        )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
