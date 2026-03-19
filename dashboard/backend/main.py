from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import os

from .auth import LoginRequest, TokenResponse, create_access_token, verify_credentials, get_current_user
from .routers import users, transactions, stats, promos

app = FastAPI(title="XRAY-VPN Dashboard", docs_url="/api/docs", redoc_url=None)

# Routers
app.include_router(users.router)
app.include_router(transactions.router)
app.include_router(stats.router)
app.include_router(promos.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    if not verify_credentials(body.login, body.password):
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
    token = create_access_token(body.login)
    return TokenResponse(access_token=token)


@app.get("/api/auth/me")
async def me(user: str = __import__("fastapi").Depends(get_current_user)):
    return {"user": user}


# Serve React SPA static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.exception_handler(StarletteHTTPException)
    async def spa_handler(request, exc):
        if exc.status_code == 404 and not request.url.path.startswith("/api"):
            return FileResponse(os.path.join(STATIC_DIR, "index.html"))
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get("/")
    async def root():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
