from fastapi import FastAPI

from .auth import LoginRequest, TokenResponse, create_access_token, verify_credentials, get_current_user
from .routers import users, transactions, stats, promos, tariffs, menus, squads, telemt, store, support, webapp_menu, webapp_payments, settings, tg_admin

BASE_PATH = "/bot/dashboard"

app = FastAPI(title="XRAY-VPN Dashboard", docs_url=f"{BASE_PATH}/api/docs", redoc_url=None)

# Routers
app.include_router(users.router, prefix=BASE_PATH)
app.include_router(transactions.router, prefix=BASE_PATH)
app.include_router(stats.router, prefix=BASE_PATH)
app.include_router(promos.router, prefix=BASE_PATH)
app.include_router(tariffs.router, prefix=BASE_PATH)
app.include_router(menus.router, prefix=BASE_PATH)
app.include_router(squads.router, prefix=BASE_PATH)
app.include_router(telemt.router, prefix=BASE_PATH)
app.include_router(store.router, prefix=BASE_PATH)
app.include_router(support.router, prefix=BASE_PATH)
app.include_router(webapp_menu.router, prefix=BASE_PATH)
app.include_router(webapp_payments.router, prefix=BASE_PATH)
app.include_router(settings.router, prefix=BASE_PATH)
app.include_router(tg_admin.router, prefix=BASE_PATH)


@app.on_event("startup")
async def ensure_schema_up_to_date():
    """Apply Alembic migrations. No-op if init container already ran them."""
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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post(f"{BASE_PATH}/api/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    if not verify_credentials(body.login, body.password):
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
    token = create_access_token(body.login)
    return TokenResponse(access_token=token)


@app.get(f"{BASE_PATH}/api/auth/me")
async def me(user: str = __import__("fastapi").Depends(get_current_user)):
    return {"user": user}

# The React SPA is built and served by the dedicated `frontend` container
# (infra/docker/frontend.Dockerfile). This service is a pure JSON API.
