"""Dashboard branding settings and public logo/PWA assets."""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import delete

from common_db.models import DashboardBrandingAsset
from common_db.repo.runtime import get_runtime_config_dict, save_runtime_config
from common_db.runtime_config import invalidate_local

from ..auth import get_current_user
from ..config import get_yaml_config
from ..database.session import async_session

router = APIRouter(prefix="/api", tags=["branding"])

MAX_LOGO_BYTES = 5 * 1024 * 1024
DEFAULT_NAME = "VPN Admin"
DEFAULT_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<rect width="512" height="512" rx="112" fill="#0c0f1a"/>
<rect x="48" y="48" width="416" height="416" rx="96" fill="#7c6cff"/>
<text x="256" y="319" text-anchor="middle" font-family="Arial,sans-serif" font-size="176" font-weight="700" fill="white">VP</text>
</svg>"""


class BrandingUpdate(BaseModel):
    branding_name: str = Field(default=DEFAULT_NAME, max_length=80)
    branding_logo_url: HttpUrl | None = None


class BrandingSettingsResponse(BaseModel):
    branding_name: str
    branding_logo_url: str
    has_custom_logo: bool
    updated_at: str | None = None


class PublicBrandingResponse(BaseModel):
    branding_name: str
    logo_url: str
    favicon_url: str
    manifest_url: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_branding_name(value: object) -> str:
    name = str(value or "").strip()
    return name[:80] or DEFAULT_NAME


def _is_public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def _validate_public_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("logo URL must use http or https")
    if parsed.username or parsed.password:
        raise ValueError("logo URL must not contain credentials")
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError("logo host could not be resolved") from exc
    if not addresses or any(not _is_public_ip(item[4][0]) for item in addresses):
        raise ValueError("logo URL must resolve only to public addresses")


def _validate_svg(content: bytes) -> None:
    lowered = content.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ValueError("SVG document types and entities are not allowed")
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise ValueError("invalid SVG") from exc
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        raise ValueError("invalid SVG root element")
    forbidden_tags = {"script", "foreignobject", "style"}
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1].lower() in forbidden_tags:
            raise ValueError("SVG contains unsupported active content")
        for raw_name, raw_value in node.attrib.items():
            name = raw_name.rsplit("}", 1)[-1].lower()
            value = raw_value.strip().lower()
            if name.startswith("on") or "javascript:" in value:
                raise ValueError("SVG contains unsupported active content")
            if name in {"href", "src"} and value and not value.startswith(("#", "data:image/")):
                raise ValueError("SVG external resources are not allowed")
            if "url(" in value and "url(#" not in value:
                raise ValueError("SVG external resources are not allowed")


def _validate_logo(content: bytes, declared_type: str) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        try:
            with Image.open(BytesIO(content)) as image:
                image.verify()
                if image.format != "PNG":
                    raise ValueError("logo must be PNG or SVG")
        except Exception as exc:
            raise ValueError("invalid PNG") from exc
        return "image/png"
    if "svg" in declared_type.lower() or content.lstrip().startswith(b"<"):
        _validate_svg(content)
        return "image/svg+xml"
    raise ValueError("logo must be PNG or SVG")


async def _download_logo(source_url: str) -> tuple[bytes, str]:
    current = source_url
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        for _ in range(4):
            await _validate_public_url(current)
            async with client.stream("GET", current, follow_redirects=False) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("logo redirect has no location")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                declared_length = response.headers.get("content-length")
                try:
                    if declared_length and int(declared_length) > MAX_LOGO_BYTES:
                        raise ValueError("logo exceeds the 5 MB limit")
                except ValueError as exc:
                    if "5 MB" in str(exc):
                        raise
                    raise ValueError("logo response has an invalid content length") from exc
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_LOGO_BYTES:
                        raise ValueError("logo exceeds the 5 MB limit")
                    chunks.append(chunk)
                content = b"".join(chunks)
                return content, _validate_logo(
                    content,
                    response.headers.get("content-type", ""),
                )
    raise ValueError("logo URL redirected too many times")


async def _read_state() -> tuple[str, str, DashboardBrandingAsset | None]:
    yaml_cfg = get_yaml_config()
    async with async_session() as session:
        config = await get_runtime_config_dict(session)
        asset = await session.get(DashboardBrandingAsset, 1)
        await session.commit()
    name = _safe_branding_name(config.get("branding_name", yaml_cfg.get("branding_name")))
    source_url = str(config.get("branding_logo_url") or "")
    return name, source_url, asset


@router.get("/branding", response_model=PublicBrandingResponse)
async def get_public_branding():
    name, _, asset = await _read_state()
    base = "/bot/dashboard/api/branding"
    version = asset.sha256[:12] if asset else "default"
    return PublicBrandingResponse(
        branding_name=name,
        logo_url=f"{base}/logo?v={version}",
        favicon_url=f"{base}/icon/64.png?v={version}",
        manifest_url=f"{base}/manifest.webmanifest",
    )


@router.get("/settings/branding", response_model=BrandingSettingsResponse)
async def get_branding_settings(_: str = Depends(get_current_user)):
    name, source_url, asset = await _read_state()
    return BrandingSettingsResponse(
        branding_name=name,
        branding_logo_url=source_url,
        has_custom_logo=asset is not None,
        updated_at=asset.updated_at if asset else None,
    )


@router.put("/settings/branding", response_model=BrandingSettingsResponse)
async def put_branding_settings(
    body: BrandingUpdate,
    user: str = Depends(get_current_user),
):
    name = _safe_branding_name(body.branding_name)
    source_url = str(body.branding_logo_url or "")
    downloaded: tuple[bytes, str] | None = None
    if source_url:
        try:
            downloaded = await _download_logo(source_url)
        except (ValueError, httpx.HTTPError) as exc:
            raise HTTPException(422, str(exc)) from exc

    async with async_session() as session:
        await save_runtime_config(
            session,
            {"branding_name": name, "branding_logo_url": source_url},
            updated_by=user,
        )
        await session.execute(delete(DashboardBrandingAsset))
        asset: DashboardBrandingAsset | None = None
        if downloaded is not None:
            content, mime_type = downloaded
            asset = DashboardBrandingAsset(
                id=1,
                source_url=source_url,
                mime_type=mime_type,
                content=content,
                sha256=hashlib.sha256(content).hexdigest(),
                updated_at=_now_iso(),
                updated_by=user,
            )
            session.add(asset)
        await session.commit()
    _render_icon.cache_clear()
    invalidate_local()
    return BrandingSettingsResponse(
        branding_name=name,
        branding_logo_url=source_url,
        has_custom_logo=asset is not None,
        updated_at=asset.updated_at if asset else None,
    )


@router.get("/branding/logo")
async def get_branding_logo():
    _, _, asset = await _read_state()
    content = asset.content if asset else DEFAULT_SVG
    mime_type = asset.mime_type if asset else "image/svg+xml"
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Cache-Control": "public, max-age=300, must-revalidate",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
            "X-Content-Type-Options": "nosniff",
        },
    )


@lru_cache(maxsize=32)
def _render_icon(
    digest: str,
    content: bytes,
    mime_type: str,
    size: int,
    maskable: bool,
) -> bytes:
    del digest
    if mime_type == "image/svg+xml":
        try:
            import cairosvg

            source = cairosvg.svg2png(bytestring=content, output_width=1024, output_height=1024)
        except (ImportError, OSError):
            fallback = Image.new("RGBA", (1024, 1024), (12, 15, 26, 255))
            draw = ImageDraw.Draw(fallback)
            draw.rounded_rectangle((96, 96, 928, 928), radius=192, fill=(124, 108, 255, 255))
            draw.polygon(
                ((224, 330), (306, 330), (374, 670), (442, 330), (524, 330), (420, 730), (328, 730)),
                fill="white",
            )
            draw.rounded_rectangle((514, 330, 804, 566), radius=112, fill="white")
            draw.rectangle((514, 442, 596, 730), fill="white")
            draw.rounded_rectangle((596, 408, 716, 488), radius=40, fill=(124, 108, 255, 255))
            source_buffer = BytesIO()
            fallback.save(source_buffer, "PNG")
            source = source_buffer.getvalue()
    else:
        source = content
    with Image.open(BytesIO(source)) as opened:
        image = opened.convert("RGBA")
    canvas_color = (12, 15, 26, 255) if maskable else (0, 0, 0, 0)
    canvas = Image.new("RGBA", (size, size), canvas_color)
    safe_size = round(size * (0.76 if maskable else 0.9))
    image.thumbnail((safe_size, safe_size), Image.Resampling.LANCZOS)
    x = (size - image.width) // 2
    y = (size - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()


@router.get("/branding/icon/{size}.png")
async def get_branding_icon(
    size: int,
    maskable: bool = Query(False),
):
    if size not in {64, 180, 192, 512}:
        raise HTTPException(404, "unsupported icon size")
    _, _, asset = await _read_state()
    content = asset.content if asset else DEFAULT_SVG
    mime_type = asset.mime_type if asset else "image/svg+xml"
    digest = asset.sha256 if asset else "default-vp"
    png = _render_icon(digest, content, mime_type, size, maskable)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300, must-revalidate"},
    )


@router.get("/branding/manifest.webmanifest")
async def get_branding_manifest():
    name, _, asset = await _read_state()
    base = "/bot/dashboard/api/branding/icon"
    version = asset.sha256[:12] if asset else "default"
    response = JSONResponse(
        content={
            "name": f"{name} Dashboard",
            "short_name": name[:30],
            "description": f"{name} admin dashboard",
            "start_url": "/bot/dashboard/",
            "scope": "/bot/dashboard/",
            "display": "standalone",
            "background_color": "#0a0a0a",
            "theme_color": "#0a0a0a",
            "icons": [
                {"src": f"{base}/192.png?v={version}", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                {"src": f"{base}/512.png?v={version}", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                {"src": f"{base}/192.png?maskable=true&v={version}", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
                {"src": f"{base}/512.png?maskable=true&v={version}", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            ],
        },
        media_type="application/manifest+json",
    )
    response.headers["Cache-Control"] = "no-cache"
    return response
