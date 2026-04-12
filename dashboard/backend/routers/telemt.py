import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from typing import Optional

from ..auth import get_current_user
from ..config import get_telemt_server, get_telemt_header

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
