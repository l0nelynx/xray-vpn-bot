import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select

from ..auth import get_current_user
from ..config import get_telemt_server, get_telemt_header
from ..database.session import async_session
from ..database.models import TelmtFreeParams

router = APIRouter(prefix="/api/telemt", tags=["telemt"])


def _base_url() -> str:
    url = get_telemt_server().rstrip("/")
    if not url:
        raise HTTPException(status_code=503, detail="telemt_server not configured")
    return url


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    header = get_telemt_header()
    if header:
        h["Authorization"] = header
    return h


@router.get("/system/info")
async def system_info(_: str = Depends(get_current_user)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{_base_url()}/v1/system/info", headers=_headers())
    return r.json()


@router.get("/health")
async def health(_: str = Depends(get_current_user)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{_base_url()}/v1/health", headers=_headers())
    return r.json()


@router.get("/stats/summary")
async def stats_summary(_: str = Depends(get_current_user)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{_base_url()}/v1/stats/summary", headers=_headers())
    return r.json()


@router.get("/stats/dcs")
async def stats_dcs(_: str = Depends(get_current_user)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{_base_url()}/v1/stats/dcs", headers=_headers())
    return r.json()


@router.get("/runtime/gates")
async def runtime_gates(_: str = Depends(get_current_user)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{_base_url()}/v1/runtime/gates", headers=_headers())
    return r.json()


@router.get("/runtime/initialization")
async def runtime_initialization(_: str = Depends(get_current_user)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{_base_url()}/v1/runtime/initialization", headers=_headers())
    return r.json()


@router.get("/security/posture")
async def security_posture(_: str = Depends(get_current_user)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{_base_url()}/v1/security/posture", headers=_headers())
    return r.json()


@router.get("/users")
async def list_users(_: str = Depends(get_current_user)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{_base_url()}/v1/users", headers=_headers())
    return r.json()


@router.get("/users/{username}")
async def get_user(username: str, _: str = Depends(get_current_user)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{_base_url()}/v1/users/{username}", headers=_headers())
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="User not found")
    return r.json()


class CreateTelmtUser(BaseModel):
    username: str
    secret: Optional[str] = None
    user_ad_tag: Optional[str] = None
    max_tcp_conns: Optional[int] = None
    expiration_rfc3339: Optional[str] = None
    data_quota_bytes: Optional[int] = None
    max_unique_ips: Optional[int] = None


@router.post("/users")
async def create_user(body: CreateTelmtUser, _: str = Depends(get_current_user)):
    payload = body.model_dump(exclude_none=True)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{_base_url()}/v1/users", headers=_headers(), json=payload)
    if r.status_code >= 400:
        data = r.json()
        detail = data.get("error", {}).get("message", r.text)
        raise HTTPException(status_code=r.status_code, detail=detail)
    return r.json()


class PatchTelmtUser(BaseModel):
    secret: Optional[str] = None
    user_ad_tag: Optional[str] = None
    max_tcp_conns: Optional[int] = None
    expiration_rfc3339: Optional[str] = None
    data_quota_bytes: Optional[int] = None
    max_unique_ips: Optional[int] = None


@router.patch("/users/{username}")
async def patch_user(username: str, body: PatchTelmtUser, _: str = Depends(get_current_user)):
    payload = body.model_dump(exclude_none=True)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.patch(f"{_base_url()}/v1/users/{username}", headers=_headers(), json=payload)
    if r.status_code >= 400:
        data = r.json()
        detail = data.get("error", {}).get("message", r.text)
        raise HTTPException(status_code=r.status_code, detail=detail)
    return r.json()


@router.delete("/users/{username}")
async def delete_user(username: str, _: str = Depends(get_current_user)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.delete(f"{_base_url()}/v1/users/{username}", headers=_headers())
    if r.status_code >= 400:
        data = r.json()
        detail = data.get("error", {}).get("message", r.text)
        raise HTTPException(status_code=r.status_code, detail=detail)
    return r.json()


# --- Telemt Free Params ---

class TelmtFreeParamsSchema(BaseModel):
    max_tcp_conns: Optional[int] = None
    max_unique_ips: Optional[int] = None
    data_quota_bytes: Optional[int] = None
    expire_days: int = 30


@router.get("/free-params", response_model=TelmtFreeParamsSchema)
async def get_free_params(_: str = Depends(get_current_user)):
    async with async_session() as session:
        row = await session.scalar(select(TelmtFreeParams).where(TelmtFreeParams.id == 1))
        if not row:
            return TelmtFreeParamsSchema()
        return TelmtFreeParamsSchema(
            max_tcp_conns=row.max_tcp_conns,
            max_unique_ips=row.max_unique_ips,
            data_quota_bytes=row.data_quota_bytes,
            expire_days=row.expire_days,
        )


@router.put("/free-params", response_model=TelmtFreeParamsSchema)
async def update_free_params(body: TelmtFreeParamsSchema, _: str = Depends(get_current_user)):
    async with async_session() as session:
        row = await session.scalar(select(TelmtFreeParams).where(TelmtFreeParams.id == 1))
        if not row:
            row = TelmtFreeParams(id=1)
            session.add(row)
        row.max_tcp_conns = body.max_tcp_conns
        row.max_unique_ips = body.max_unique_ips
        row.data_quota_bytes = body.data_quota_bytes
        row.expire_days = body.expire_days
        await session.commit()
        await session.refresh(row)
    return TelmtFreeParamsSchema(
        max_tcp_conns=row.max_tcp_conns,
        max_unique_ips=row.max_unique_ips,
        data_quota_bytes=row.data_quota_bytes,
        expire_days=row.expire_days,
    )
