from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import os

from .auth import LoginRequest, TokenResponse, create_access_token, verify_credentials, get_current_user
from .routers import users, transactions, stats, promos, tariffs, menus, squads, telemt, store, support, webapp_menu, webapp_payments

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


@app.on_event("startup")
async def ensure_schema_up_to_date():
    """Apply Alembic migrations. No-op if init container already ran them."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from migrations_runner import upgrade_to_head
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


# Serve React SPA static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

if os.path.isdir(STATIC_DIR):
    assets_dir = os.path.join(STATIC_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount(f"{BASE_PATH}/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.exception_handler(StarletteHTTPException)
    async def spa_handler(request, exc):
        if exc.status_code == 404 and not request.url.path.startswith(f"{BASE_PATH}/api"):
            return FileResponse(os.path.join(STATIC_DIR, "index.html"))
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get(BASE_PATH)
    @app.get(f"{BASE_PATH}/{{rest:path}}")
    async def root(rest: str = ""):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
