import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from .config import get_expose_api_docs, get_log_level, get_web_allowed_origins
from .security_config import validate_security_config

logging.basicConfig(
    level=get_log_level(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
from .android import auth_router as android_auth_router
from .android import data_router as android_data_router
from .android import email_router as android_email_router
from .android import iap_router as android_iap_router
from .android import link_router as android_link_router
from .android import payments_router as android_payments_router
from .android import promo_router as android_promo_router
from .android import subscription_router as android_subscription_router
from .android import support_router as android_support_router
from .connect.router import router as connect_router
from .routers import devices, free, me, menu, payments, promo, support
from .web import web_router

BASE_PATH = "/bot/miniapp"

# Reuse the auth router's limiter so per-route decorators on it take effect.
limiter = android_auth_router.limiter


def _run_migrations() -> None:
    """Bring the shared Postgres schema to head via Alembic. Whichever service
    boots first applies them; subsequent boots are no-ops. If alembic config
    isn't bundled in this image, the bot or dashboard service owns migrations."""
    try:
        from migrations_runner import upgrade_to_head
    except ImportError:
        return
    upgrade_to_head()
    # Страховка: если что-то по дороге всё-таки дёрнуло fileConfig() и
    # выключило ранее заведённые логгеры — реактивируем их и заново ставим
    # хэндлер на корне. force=True гарантирует, что повторный basicConfig
    # не будет проигнорирован.
    for name in list(logging.Logger.manager.loggerDict):
        lg = logging.getLogger(name)
        if isinstance(lg, logging.Logger):
            lg.disabled = False
    logging.basicConfig(
        level=get_log_level(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_security_config()
    _run_migrations()
    yield


# Swagger UI / openapi.json are gated behind a config flag — off in production so
# the full API surface (incl. admin/IAP routes) isn't publicly enumerable.
_expose_docs = get_expose_api_docs()
app = FastAPI(
    title="XRAY-VPN MiniApp",
    docs_url=f"{BASE_PATH}/api/docs" if _expose_docs else None,
    openapi_url=f"{BASE_PATH}/openapi.json" if _expose_docs else None,
    redoc_url=None,
    lifespan=lifespan,
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
app.include_router(connect_router, prefix=BASE_PATH)


@app.get("/health")
async def health():
    return {"status": "ok"}


# The React SPA (Telegram MiniApp + web portal) is built and served by the
# dedicated `frontend` container (infra/docker/frontend.Dockerfile). This
# service is a pure JSON API.
