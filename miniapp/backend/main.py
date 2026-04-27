import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from .database.session import engine
from .routers import me, support

BASE_PATH = "/bot/miniapp"

app = FastAPI(
    title="XRAY-VPN MiniApp",
    docs_url=f"{BASE_PATH}/api/docs",
    redoc_url=None,
)

app.include_router(me.router, prefix=BASE_PATH)
app.include_router(support.router, prefix=BASE_PATH)


@app.on_event("startup")
async def ensure_support_tables():
    async with engine.begin() as conn:
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


# Serve frontend SPA
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
