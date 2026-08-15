from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import DashboardBrandingAsset
from dashboard.backend.routers import branding


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGBA", (64, 32), (124, 108, 255, 255)).save(output, "PNG")
    return output.getvalue()


def test_branding_logo_validation_and_icon_rendering() -> None:
    png = _png_bytes()
    assert branding._validate_logo(png, "application/octet-stream") == "image/png"
    icon = branding._render_icon("test", png, "image/png", 192, False)
    with Image.open(BytesIO(icon)) as image:
        assert image.size == (192, 192)

    with pytest.raises(ValueError, match="active content"):
        branding._validate_svg(b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>')

    default_icon = branding._render_icon(
        "default-test",
        branding.DEFAULT_SVG,
        "image/svg+xml",
        192,
        False,
    )
    with Image.open(BytesIO(default_icon)) as image:
        assert image.size == (192, 192)
        assert any(pixel[:3] == (255, 255, 255) for pixel in image.get_flattened_data())


def test_branding_blocks_private_network_targets() -> None:
    assert branding._is_public_ip("8.8.8.8") is True
    assert branding._is_public_ip("127.0.0.1") is False
    assert branding._is_public_ip("10.0.0.1") is False
    assert branding._is_public_ip("::1") is False


def test_branding_save_persists_snapshot_and_public_metadata(monkeypatch) -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            monkeypatch.setattr(branding, "async_session", Session)
            monkeypatch.setattr(branding, "get_yaml_config", lambda: {})

            async def fake_download(_: str) -> tuple[bytes, str]:
                return _png_bytes(), "image/png"

            monkeypatch.setattr(branding, "_download_logo", fake_download)
            body = branding.BrandingUpdate(
                branding_name="Acme VPN",
                branding_logo_url="https://cdn.example.com/logo.png",
            )
            saved = await branding.put_branding_settings(body, user="admin")
            assert saved.branding_name == "Acme VPN"
            assert saved.has_custom_logo is True

            public = await branding.get_public_branding()
            assert public.branding_name == "Acme VPN"
            assert "/api/branding/logo?v=" in public.logo_url

            async with Session() as session:
                asset = await session.get(DashboardBrandingAsset, 1)
                assert asset is not None
                assert asset.source_url == "https://cdn.example.com/logo.png"
        finally:
            await engine.dispose()

    asyncio.run(go())
