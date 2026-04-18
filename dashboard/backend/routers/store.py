import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from ..auth import get_current_user
from ..config import get_store_url, get_store_api_token

router = APIRouter(prefix="/api/store", tags=["store"])


def _base_url() -> str:
    url = get_store_url().rstrip("/")
    if not url:
        raise HTTPException(status_code=503, detail="store_url not configured")
    return url


def _headers() -> dict:
    token = get_store_api_token()
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


@router.get("/order-params")
async def list_order_params(
    item_id: Optional[int] = Query(None),
    _: str = Depends(get_current_user),
):
    params = {}
    if item_id is not None:
        params["item_id"] = item_id
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{_base_url()}/store/api/order-params/",
            headers=_headers(),
            params=params,
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


class OrderParamCreate(BaseModel):
    item_id: int
    param_id: int
    user_data_id: int
    type: str
    data: str


@router.post("/order-params")
async def create_order_param(body: OrderParamCreate, _: str = Depends(get_current_user)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{_base_url()}/store/api/order-params/",
            headers=_headers(),
            json=body.model_dump(),
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


class OrderParamUpdate(BaseModel):
    item_id: Optional[int] = None
    param_id: Optional[int] = None
    user_data_id: Optional[int] = None
    type: Optional[str] = None
    data: Optional[str] = None


@router.put("/order-params/{param_id}")
async def update_order_param(param_id: int, body: OrderParamUpdate, _: str = Depends(get_current_user)):
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.put(
            f"{_base_url()}/store/api/order-params/{param_id}",
            headers=_headers(),
            json=payload,
        )
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="OrderParam not found")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@router.delete("/order-params/{param_id}")
async def delete_order_param(param_id: int, _: str = Depends(get_current_user)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.delete(
            f"{_base_url()}/store/api/order-params/{param_id}",
            headers=_headers(),
        )
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="OrderParam not found")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()
