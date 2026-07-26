from contextlib import asynccontextmanager
import logging

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import login_guard
from .auth import (
    LoginRequest,
    TokenResponse,
    create_access_token,
    get_current_user,
    validate_security_config,
    verify_credentials,
)
from .config import get_expose_api_docs, get_redis_url, get_payments_secrets_key, get_yaml_config
from .routers import (
    users,
    transactions,
    stats,
    promos,
    menus,
    telemt,
    store,
    support,
    webapp_menu,
    webapp_payments,
    settings,
    runtime_settings,
    payment_integrations,
    app_integrations,
    tg_admin,
    crm,
    push,
    giveaways,
)

BASE_PATH = "/bot/dashboard"
logger = logging.getLogger(__name__)


def _migrate_schema() -> None:
    """Apply Alembic migrations. No-op if the init container already ran them."""
    import sys
    from pathlib import Path
    # Make migrations_runner importable in both layouts without a fixed parent
    # index: the flat container (/app, already on sys.path) and the source tree
    # (services/dashboard/backend -> repo root). Walk up to the dir that has it.
    for parent in Path(__file__).resolve().parents:
        if (parent / "migrations_runner.py").exists():
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            break
    try:
        from migrations_runner import upgrade_to_head
    except ImportError:
        return
    upgrade_to_head()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail closed FIRST: never serve a panel whose admin tokens can be forged
    # with a default/weak secret. Raises → boot aborts.
    validate_security_config()
    _migrate_schema()
    import asyncio
    from .database.session import async_session
    from common_db.runtime_config import bootstrap_runtime_overlay, runtime_overlay_poll_loop

    yaml_cfg = get_yaml_config()
    await bootstrap_runtime_overlay(
        async_session,
        yaml_cfg,
        crypto_secret=get_payments_secrets_key(),
    )
    poll_task = asyncio.create_task(runtime_overlay_poll_loop(async_session))

    pool = None
    try:
        pool = await create_pool(RedisSettings.from_dsn(get_redis_url()))
    except Exception as exc:
        logger.warning("ARQ Redis pool unavailable — CRM enqueue disabled: %s", exc)
    app.state.arq_pool = pool
    try:
        yield
    finally:
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass
        if pool is not None:
            await pool.close()


# Swagger UI + openapi.json gated behind a flag — off in production so the admin
# API surface isn't publicly enumerable. openapi_url must also be disabled, else
# the schema stays reachable at the default /openapi.json.
_expose_docs = get_expose_api_docs()
app = FastAPI(
    title="XRAY-VPN Dashboard",
    docs_url=f"{BASE_PATH}/api/docs" if _expose_docs else None,
    openapi_url=f"{BASE_PATH}/openapi.json" if _expose_docs else None,
    redoc_url=None,
    lifespan=lifespan,
)

# Routers
app.include_router(users.router, prefix=BASE_PATH)
app.include_router(transactions.router, prefix=BASE_PATH)
app.include_router(stats.router, prefix=BASE_PATH)
app.include_router(promos.router, prefix=BASE_PATH)
app.include_router(menus.router, prefix=BASE_PATH)
app.include_router(telemt.router, prefix=BASE_PATH)
app.include_router(store.router, prefix=BASE_PATH)
app.include_router(support.router, prefix=BASE_PATH)
app.include_router(webapp_menu.router, prefix=BASE_PATH)
app.include_router(webapp_payments.router, prefix=BASE_PATH)
app.include_router(settings.router, prefix=BASE_PATH)
app.include_router(runtime_settings.router, prefix=BASE_PATH)
app.include_router(payment_integrations.router, prefix=BASE_PATH)
app.include_router(app_integrations.router, prefix=BASE_PATH)
app.include_router(tg_admin.router, prefix=BASE_PATH)
app.include_router(crm.router, prefix=BASE_PATH)
app.include_router(push.router, prefix=BASE_PATH)
app.include_router(giveaways.router, prefix=BASE_PATH)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post(f"{BASE_PATH}/api/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request):
    # Throttle per real client IP to stop unlimited admin-password guessing.
    ip = login_guard.real_client_ip(request)
    login_guard.check(ip)
    if not verify_credentials(body.login, body.password):
        login_guard.record_fail(ip)
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
    login_guard.clear(ip)
    token = create_access_token(body.login)
    return TokenResponse(access_token=token)


@app.get(f"{BASE_PATH}/api/auth/me")
async def me(user: str = __import__("fastapi").Depends(get_current_user)):
    return {"user": user}

# The React SPA is built and served by the dedicated `frontend` container
# (infra/docker/frontend.Dockerfile). This service is a pure JSON API.
