import asyncio
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from ..auth import get_current_user
from ..config import get_telemt_server, get_telemt_header
from ..database.session import async_session
# Singleton auto-seed lives in common_db.repo.system. Use it so the GET
# always returns the canonical defaults (expire_days=30) on a fresh DB.
from common_db.repo import system as _repo_system

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


async def _telemt_request(
    method: str,
    path: str,
    *,
    json_body: Optional[dict[str, Any]] = None,
    expected_not_found: Optional[str] = None,
    extra_headers: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    url = f"{_base_url()}{path}"
    headers = _headers()
    if extra_headers:
        headers.update(extra_headers)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.request(method, url, headers=headers, json=json_body)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Telemt unavailable: {exc}") from exc

    data: dict[str, Any]
    try:
        data = r.json()
    except ValueError:
        data = {"ok": False, "error": {"message": r.text or "Invalid response from telemt"}}

    if r.status_code == 404 and expected_not_found:
        raise HTTPException(status_code=404, detail=expected_not_found)
    if r.status_code >= 400:
        detail = data.get("error", {}).get("message", r.text)
        raise HTTPException(status_code=r.status_code, detail=detail)
    return data


@router.get("/health")
async def health(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/health")


@router.get("/health/ready")
async def health_ready(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/health/ready")


@router.get("/system/info")
async def system_info(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/system/info")


@router.get("/runtime/gates")
async def runtime_gates(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/runtime/gates")


@router.get("/runtime/initialization")
async def runtime_initialization(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/runtime/initialization")


@router.get("/runtime/me-pool-state")
async def runtime_me_pool_state(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/runtime/me_pool_state")


@router.get("/runtime/me-quality")
async def runtime_me_quality(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/runtime/me_quality")


@router.get("/runtime/upstream-quality")
async def runtime_upstream_quality(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/runtime/upstream_quality")


@router.get("/runtime/nat-stun")
async def runtime_nat_stun(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/runtime/nat_stun")


@router.get("/runtime/me-selftest")
async def runtime_me_selftest(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/runtime/me-selftest")


@router.get("/runtime/connections/summary")
async def runtime_connections_summary(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/runtime/connections/summary")


@router.get("/runtime/events/recent")
async def runtime_events_recent(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/runtime/events/recent")


@router.get("/runtime/tls-fingerprints")
async def runtime_tls_fingerprints(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/runtime/tls-fingerprints")


@router.get("/limits/effective")
async def limits_effective(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/limits/effective")


@router.get("/security/posture")
async def security_posture(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/security/posture")


@router.get("/security/whitelist")
async def security_whitelist(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/security/whitelist")


@router.get("/stats/summary")
async def stats_summary(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/stats/summary")


@router.get("/stats/dcs")
async def stats_dcs(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/stats/dcs")


@router.get("/stats/zero/all")
async def stats_zero_all(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/stats/zero/all")


@router.get("/stats/upstreams")
async def stats_upstreams(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/stats/upstreams")


@router.get("/stats/minimal/all")
async def stats_minimal_all(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/stats/minimal/all")


@router.get("/stats/me-writers")
async def stats_me_writers(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/stats/me-writers")


@router.get("/stats/users")
async def stats_users(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/stats/users")


@router.get("/stats/users/active-ips")
async def stats_users_active_ips(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/stats/users/active-ips")


# Telemt GET/PATCH /v1/config manages these full top-level sections plus a
# field-level allowlist under ``server`` (see telemt PR #878).  Keep the nested
# allowlist here as a defence in depth: the dashboard must never proxy
# server.api credentials or per-node bind identity even if an upstream returns
# more than its documented managed-config view.
_EDITABLE_CONFIG_SECTIONS = frozenset(
    {
        "general",
        "timeouts",
        "censorship",
        "upstreams",
        "dc_overrides",
        "server",
    }
)
_EDITABLE_SERVER_FIELDS = frozenset({"listeners"})


def _filter_editable_config(data: Any) -> Any:
    """Keep only Telemt-managed sections from a GET /v1/config payload."""
    if not isinstance(data, dict):
        return data
    filtered = {
        key: value
        for key, value in data.items()
        if key in _EDITABLE_CONFIG_SECTIONS and key != "server"
    }
    server = data.get("server")
    if isinstance(server, dict):
        filtered_server = {
            key: value
            for key, value in server.items()
            if key in _EDITABLE_SERVER_FIELDS
        }
        # Telemt omits the partial server view when it has no editable fields.
        if filtered_server:
            filtered["server"] = filtered_server
    return filtered


def _assert_editable_patch(payload: dict[str, Any]) -> None:
    if "access" in payload:
        raise HTTPException(
            status_code=400,
            detail="access is not editable here; manage users via the Telemt Users API",
        )
    unknown = sorted(set(payload) - _EDITABLE_CONFIG_SECTIONS)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                "section not editable via Telemt API: "
                + ", ".join(unknown)
                + ". Allowed: "
                + ", ".join(sorted(_EDITABLE_CONFIG_SECTIONS))
            ),
        )
    if "server" not in payload:
        return

    server = payload["server"]
    if not isinstance(server, dict):
        raise HTTPException(status_code=400, detail="server patch must be a JSON object")
    if not server:
        raise HTTPException(
            status_code=400,
            detail="empty server patch: provide server.listeners",
        )
    unknown_server_fields = sorted(set(server) - _EDITABLE_SERVER_FIELDS)
    if unknown_server_fields:
        raise HTTPException(
            status_code=400,
            detail=(
                "field not editable via Telemt API: "
                + ", ".join(f"server.{field}" for field in unknown_server_fields)
                + ". Allowed under server: "
                + ", ".join(sorted(_EDITABLE_SERVER_FIELDS))
            ),
        )
    listeners = server.get("listeners")
    if not isinstance(listeners, list):
        raise HTTPException(
            status_code=400,
            detail="server.listeners must be an array (the array is replaced wholesale)",
        )
    if any(not isinstance(listener, dict) for listener in listeners):
        raise HTTPException(
            status_code=400,
            detail="each server.listeners item must be a JSON object",
        )


@router.get("/config")
async def get_config(_: str = Depends(get_current_user)):
    raw = await _telemt_request("GET", "/v1/config")
    if isinstance(raw, dict) and "data" in raw:
        return {**raw, "data": _filter_editable_config(raw.get("data"))}
    return _filter_editable_config(raw)


@router.patch("/config")
async def patch_config(body: dict[str, Any], _: str = Depends(get_current_user)):
    """Sparse patch of Telemt-managed config sections only."""
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Config patch must be a JSON object")
    payload = dict(body)
    revision = payload.pop("revision", None)
    if revision is not None and not isinstance(revision, str):
        raise HTTPException(status_code=400, detail="revision must be a string")
    if not payload:
        raise HTTPException(
            status_code=400,
            detail="Empty patch: provide at least one of "
            + ", ".join(sorted(_EDITABLE_CONFIG_SECTIONS)),
        )
    _assert_editable_patch(payload)
    extra = {}
    if revision:
        extra["If-Match"] = revision
    return await _telemt_request("PATCH", "/v1/config", json_body=payload, extra_headers=extra or None)


@router.get("/users")
async def list_users(_: str = Depends(get_current_user)):
    return await _telemt_request("GET", "/v1/users")


@router.get("/users/quota")
async def users_quota(_: str = Depends(get_current_user)):
    try:
        return await _telemt_request("GET", "/v1/users/quota")
    except HTTPException as exc:
        # Older Telemt builds (< PR #788) have no /v1/users/quota route yet.
        if exc.status_code == 404:
            return {"ok": True, "data": {"users": []}}
        raise


@router.get("/users/{username}")
async def get_user(username: str, _: str = Depends(get_current_user)):
    return await _telemt_request("GET", f"/v1/users/{username}", expected_not_found="User not found")


class CreateTelmtUser(BaseModel):
    username: str
    secret: Optional[str] = None
    user_ad_tag: Optional[str] = None
    max_tcp_conns: Optional[int] = None
    expiration_rfc3339: Optional[str] = None
    data_quota_bytes: Optional[int] = None
    max_unique_ips: Optional[int] = None
    rate_limit_up_bps: Optional[int] = None
    rate_limit_down_bps: Optional[int] = None


@router.post("/users")
async def create_user(body: CreateTelmtUser, _: str = Depends(get_current_user)):
    payload = body.model_dump(exclude_none=True)
    return await _telemt_request("POST", "/v1/users", json_body=payload)


class PatchTelmtUser(BaseModel):
    secret: Optional[str] = None
    user_ad_tag: Optional[str] = None
    max_tcp_conns: Optional[int] = None
    expiration_rfc3339: Optional[str] = None
    data_quota_bytes: Optional[int] = None
    max_unique_ips: Optional[int] = None
    rate_limit_up_bps: Optional[int] = None
    rate_limit_down_bps: Optional[int] = None


@router.patch("/users/{username}")
async def patch_user(username: str, body: PatchTelmtUser, _: str = Depends(get_current_user)):
    payload = body.model_dump(exclude_none=True)
    return await _telemt_request("PATCH", f"/v1/users/{username}", json_body=payload)


@router.delete("/users/{username}")
async def delete_user(username: str, _: str = Depends(get_current_user)):
    return await _telemt_request("DELETE", f"/v1/users/{username}")


@router.post("/users/{username}/rotate-secret")
async def rotate_user_secret(username: str, _: str = Depends(get_current_user)):
    return await _telemt_request("POST", f"/v1/users/{username}/rotate-secret", json_body={})


@router.post("/users/{username}/enable")
async def enable_user(username: str, _: str = Depends(get_current_user)):
    return await _telemt_request("POST", f"/v1/users/{username}/enable", json_body={})


@router.post("/users/{username}/disable")
async def disable_user(username: str, _: str = Depends(get_current_user)):
    return await _telemt_request("POST", f"/v1/users/{username}/disable", json_body={})


@router.post("/users/{username}/reset-quota")
async def reset_user_quota(username: str, _: str = Depends(get_current_user)):
    return await _telemt_request("POST", f"/v1/users/{username}/reset-quota", json_body={})


class BulkUsersRequest(BaseModel):
    usernames: list[str]


class BulkExtendRequest(BulkUsersRequest):
    expiration_rfc3339: str


class BulkUpdateLimitsRequest(BulkUsersRequest):
    max_tcp_conns: Optional[int] = None
    max_unique_ips: Optional[int] = None
    data_quota_bytes: Optional[int] = None
    rate_limit_up_bps: Optional[int] = None
    rate_limit_down_bps: Optional[int] = None


async def _bulk_user_action(
    usernames: list[str],
    action_coro,
) -> dict[str, Any]:
    if not usernames:
        raise HTTPException(status_code=400, detail="No usernames provided")
    sem = asyncio.Semaphore(20)
    errors: list[dict[str, Any]] = []
    succeeded = 0

    async def run_for_user(username: str):
        nonlocal succeeded
        async with sem:
            try:
                await action_coro(username)
                succeeded += 1
            except HTTPException as exc:
                errors.append({"username": username, "status": exc.status_code, "detail": exc.detail})
            except Exception as exc:  # noqa: BLE001
                errors.append({"username": username, "status": 500, "detail": str(exc)})

    await asyncio.gather(*(run_for_user(u) for u in usernames))
    return {
        "processed": len(usernames),
        "succeeded": succeeded,
        "failed": len(errors),
        "errors": errors,
    }


@router.post("/users/bulk-delete")
async def bulk_delete_users(body: BulkUsersRequest, _: str = Depends(get_current_user)):
    return await _bulk_user_action(body.usernames, lambda username: _telemt_request("DELETE", f"/v1/users/{username}"))


@router.post("/users/bulk-extend")
async def bulk_extend_users(body: BulkExtendRequest, _: str = Depends(get_current_user)):
    async def _extend(username: str):
        await _telemt_request(
            "PATCH",
            f"/v1/users/{username}",
            json_body={"expiration_rfc3339": body.expiration_rfc3339},
        )

    return await _bulk_user_action(body.usernames, _extend)


@router.post("/users/bulk-rotate-secret")
async def bulk_rotate_secrets(body: BulkUsersRequest, _: str = Depends(get_current_user)):
    return await _bulk_user_action(
        body.usernames,
        lambda username: _telemt_request("POST", f"/v1/users/{username}/rotate-secret", json_body={}),
    )


@router.post("/users/bulk-update-limits")
async def bulk_update_limits(body: BulkUpdateLimitsRequest, _: str = Depends(get_current_user)):
    patch_payload = body.model_dump(exclude={"usernames"}, exclude_none=True)
    if not patch_payload:
        raise HTTPException(status_code=400, detail="No limits provided")

    async def _patch(username: str):
        await _telemt_request("PATCH", f"/v1/users/{username}", json_body=patch_payload)

    return await _bulk_user_action(body.usernames, _patch)


@router.post("/users/bulk-enable")
async def bulk_enable_users(body: BulkUsersRequest, _: str = Depends(get_current_user)):
    return await _bulk_user_action(
        body.usernames,
        lambda username: _telemt_request("POST", f"/v1/users/{username}/enable", json_body={}),
    )


@router.post("/users/bulk-disable")
async def bulk_disable_users(body: BulkUsersRequest, _: str = Depends(get_current_user)):
    return await _bulk_user_action(
        body.usernames,
        lambda username: _telemt_request("POST", f"/v1/users/{username}/disable", json_body={}),
    )


# --- Telemt Free Params ---

class TelmtFreeParamsSchema(BaseModel):
    max_tcp_conns: Optional[int] = None
    max_unique_ips: Optional[int] = None
    data_quota_bytes: Optional[int] = None
    expire_days: int = 30
    rate_limit_up_bps: Optional[int] = None
    rate_limit_down_bps: Optional[int] = None


@router.get("/free-params", response_model=TelmtFreeParamsSchema)
async def get_free_params(_: str = Depends(get_current_user)):
    async with async_session() as session:
        row = await _repo_system.get_telmt_free_params(session)
        await session.commit()  # persist auto-seed
        return TelmtFreeParamsSchema(
            max_tcp_conns=row.max_tcp_conns,
            max_unique_ips=row.max_unique_ips,
            data_quota_bytes=row.data_quota_bytes,
            expire_days=row.expire_days,
            rate_limit_up_bps=row.rate_limit_up_bps,
            rate_limit_down_bps=row.rate_limit_down_bps,
        )


@router.put("/free-params", response_model=TelmtFreeParamsSchema)
async def update_free_params(body: TelmtFreeParamsSchema, _: str = Depends(get_current_user)):
    async with async_session() as session:
        row = await _repo_system.get_telmt_free_params(session)
        row.max_tcp_conns = body.max_tcp_conns
        row.max_unique_ips = body.max_unique_ips
        row.data_quota_bytes = body.data_quota_bytes
        row.expire_days = body.expire_days
        row.rate_limit_up_bps = body.rate_limit_up_bps
        row.rate_limit_down_bps = body.rate_limit_down_bps
        await session.commit()
        await session.refresh(row)
    return TelmtFreeParamsSchema(
        max_tcp_conns=row.max_tcp_conns,
        max_unique_ips=row.max_unique_ips,
        data_quota_bytes=row.data_quota_bytes,
        expire_days=row.expire_days,
        rate_limit_up_bps=row.rate_limit_up_bps,
        rate_limit_down_bps=row.rate_limit_down_bps,
    )
