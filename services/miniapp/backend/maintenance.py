"""Maintenance gate for MiniApp / web / Android HTTP APIs."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from common_db.runtime_config import get_maintenance, is_maintenance_enabled

# Paths that stay reachable during maintenance (health / docs / static).
_ALLOW_SUFFIXES = (
    "/health",
    "/openapi.json",
    "/api/docs",
)


class MaintenanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.endswith(sfx) or sfx in path for sfx in _ALLOW_SUFFIXES):
            return await call_next(request)
        # Always allow OPTIONS (CORS preflight).
        if request.method == "OPTIONS":
            return await call_next(request)
        if not is_maintenance_enabled():
            return await call_next(request)
        maint = get_maintenance()
        return JSONResponse(
            status_code=503,
            content={
                "detail": "maintenance",
                "maintenance": True,
                "title": maint.get("title") or "Технические работы",
                "text": maint.get("text") or "Сервис временно недоступен.",
            },
        )
