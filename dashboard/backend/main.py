from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import os

from sqlalchemy import text

from .auth import LoginRequest, TokenResponse, create_access_token, verify_credentials, get_current_user
from .database.session import engine
from .routers import users, transactions, stats, promos, tariffs, menus, squads, telemt, store, support

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


async def _has_column(conn, table: str, column: str) -> bool:
    rows = (await conn.execute(text(f"PRAGMA table_info({table})"))).all()
    return any(r[1] == column for r in rows)


async def _table_exists(conn, table: str) -> bool:
    row = (await conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": table},
    )).first()
    return row is not None


@app.on_event("startup")
async def ensure_support_tables():
    async with engine.begin() as conn:
        if await _table_exists(conn, "support_tickets"):
            required = ["user_id", "username", "subject", "message", "status",
                        "created_at", "updated_at"]
            if not all([await _has_column(conn, "support_tickets", c) for c in required]):
                await conn.execute(text("DROP TABLE IF EXISTS support_messages"))
                await conn.execute(text("DROP TABLE support_tickets"))
        if await _table_exists(conn, "support_messages") and \
                not await _has_column(conn, "support_messages", "ticket_id"):
            await conn.execute(text("DROP TABLE support_messages"))

        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS support_tickets ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " user_id INTEGER NOT NULL REFERENCES users(id),"
            " username VARCHAR(100),"
            " subject VARCHAR(200) NOT NULL,"
            " message TEXT NOT NULL,"
            " status VARCHAR(20) NOT NULL DEFAULT 'open',"
            " created_at VARCHAR(30) NOT NULL,"
            " updated_at VARCHAR(30) NOT NULL)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_support_tickets_user_id ON support_tickets(user_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_support_tickets_status ON support_tickets(status)"
        ))
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS support_messages ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,"
            " sender VARCHAR(20) NOT NULL,"
            " text TEXT NOT NULL,"
            " created_at VARCHAR(30) NOT NULL)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_support_messages_ticket_id ON support_messages(ticket_id)"
        ))


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
