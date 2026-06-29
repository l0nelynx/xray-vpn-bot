import logging
import os

from fastapi import FastAPI

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import get_web_allowed_origins
from .android import auth_router as android_auth_router
from .android import data_router as android_data_router
from .android import email_router as android_email_router
from .android import iap_router as android_iap_router
from .android import link_router as android_link_router
from .android import payments_router as android_payments_router
from .android import promo_router as android_promo_router
from .android import subscription_router as android_subscription_router
from .android import support_router as android_support_router
from .routers import devices, free, me, menu, payments, promo, support
from .web import web_router

BASE_PATH = "/bot/miniapp"

# Reuse the auth router's limiter so per-route decorators on it take effect.
limiter = android_auth_router.limiter

app = FastAPI(
    title="XRAY-VPN MiniApp",
    docs_url=f"{BASE_PATH}/api/docs",
    openapi_url=f"{BASE_PATH}/openapi.json",
    redoc_url=None,
)
app.state.limiter = limiter

# CORS for the external web portal (separate static hosting)
_cors_origins = get_web_allowed_origins()
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request, exc):
    return JSONResponse(status_code=429, content={"detail": {"code": "rate_limited"}})


app.include_router(me.router, prefix=BASE_PATH)
app.include_router(support.router, prefix=BASE_PATH)
app.include_router(devices.router, prefix=BASE_PATH)
app.include_router(payments.router, prefix=BASE_PATH)
app.include_router(menu.router, prefix=BASE_PATH)
app.include_router(promo.router, prefix=BASE_PATH)
app.include_router(free.router, prefix=BASE_PATH)
app.include_router(android_auth_router.router, prefix=BASE_PATH)
app.include_router(android_email_router.router, prefix=BASE_PATH)
app.include_router(android_payments_router.router, prefix=BASE_PATH)
app.include_router(android_iap_router.router, prefix=BASE_PATH)
app.include_router(android_data_router.router, prefix=BASE_PATH)
app.include_router(android_link_router.router, prefix=BASE_PATH)
app.include_router(android_subscription_router.router, prefix=BASE_PATH)
app.include_router(android_promo_router.router, prefix=BASE_PATH)
app.include_router(android_support_router.router, prefix=BASE_PATH)
app.include_router(web_router.router, prefix=BASE_PATH)


@app.on_event("startup")
async def ensure_support_tables():
    """Run Alembic migrations.

    Schema management lives in alembic/. Any service that boots first will
    bring the shared SQLite forward; subsequent boots are no-ops.
    """
    try:
        from migrations_runner import upgrade_to_head
    except ImportError:
        # If alembic config is not bundled in this image, the bot or dashboard
        # service is responsible for migrations.
        return
    upgrade_to_head()
    # Страховка: если что-то по дороге всё-таки дёрнуло fileConfig() и
    # выключило ранее заведённые логгеры — реактивируем их и заново
    # ставим хэндлер на корне. force=True гарантирует, что повторный
    # basicConfig не будет проигнорирован.
    for name in list(logging.Logger.manager.loggerDict):
        lg = logging.getLogger(name)
        if isinstance(lg, logging.Logger):
            lg.disabled = False
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve Telegram MiniApp SPA
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

if os.path.isdir(STATIC_DIR):
    assets_dir = os.path.join(STATIC_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount(f"{BASE_PATH}/assets", StaticFiles(directory=assets_dir), name="assets")

    _miniapp_html = os.path.join(STATIC_DIR, "index.html")

    @app.exception_handler(StarletteHTTPException)
    async def spa_handler(request, exc):
        if exc.status_code == 404:
            path = request.url.path
            if path.startswith(BASE_PATH) and not path.startswith(f"{BASE_PATH}/api"):
                if os.path.isfile(_miniapp_html):
                    return FileResponse(_miniapp_html)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get(BASE_PATH)
    @app.get(f"{BASE_PATH}/{{rest:path}}")
    async def root(rest: str = ""):
        return FileResponse(_miniapp_html)
