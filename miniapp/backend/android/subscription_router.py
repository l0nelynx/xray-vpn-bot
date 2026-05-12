"""Unauthenticated subscription-lookup endpoint for Android.

`/api/android/check-uuid` lets the app verify that a `short_uuid` collected
from a subscription link belongs to a real Remnawave user — used during
onboarding so the client can decide whether to offer "recover existing
subscription" flows before forcing email registration.

Sits outside auth_router because it's intentionally unauthenticated, like
`/register` and `/login`, but uses a different prefix (`/api/android`).
Rate-limited because the upstream Remnawave call is not free.
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..remnawave_client import get_user_by_short_uuid_raw
from .auth_router import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/android", tags=["android-subscription"])

# Remnawave short_uuid is a URL-safe slug; in practice 8-32 chars. Allow a
# generous superset to avoid breaking on SDK changes, but reject anything
# that obviously can't be a slug (whitespace, slashes) so we don't forward
# nonsense to Remnawave.
_SHORT_UUID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


class CheckUuidRequest(BaseModel):
    short_uuid: str = Field(..., min_length=6, max_length=64)


@router.post("/check-uuid")
@limiter.limit("10/minute")
async def check_uuid(req: CheckUuidRequest, request: Request) -> dict:
    """Return the full Remnawave SDK DTO for the user matching `short_uuid`,
    or 404 if no such user exists.

    Response shape is exactly what `RemnawaveSDK.users.get_user_by_short_uuid`
    returns (model_dump with aliases), so the client sees every upstream
    field without backend interpretation.
    """
    if not _SHORT_UUID_RE.match(req.short_uuid):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "bad_short_uuid"},
        )
    data = await get_user_by_short_uuid_raw(req.short_uuid)
    if data is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found"},
        )
    return data
