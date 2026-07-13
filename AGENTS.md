# AGENTS.md

## Cursor Cloud specific instructions

This repo is a Telegram VPN sales bot suite (Remnawave-backed) with three services. Standard setup/run commands live in `README.md`; this section only captures the non-obvious, durable gotchas for developing here in the cloud VM. The update script already installs dependencies on startup — do not re-run installs manually.

### Services (what runs where)
- **seller-bot** (`main.py`): main user bot + payment webhooks (uvicorn on `:5000`) + optional admin bot + CryptoBot polling.
- **support-bot** (`support.py`): standalone support conversation bot (long-polling, no port).
- **dashboard** (`dashboard/`): React (Vite) SPA + FastAPI backend admin panel, mounted at base path `/bot/dashboard`.
- All three share **one SQLite file** (`db.sqlite3`). There is **no lint/test suite** in this repo; the only build step is the frontend (`npm run build` = `tsc && vite build`).

### Two separate Python venvs (do NOT merge)
The root and dashboard requirements pin **conflicting** versions of `fastapi`/`pydantic`, so they are installed into two venvs by the update script:
- `venv/` — seller-bot + support-bot (`requirements.txt`).
- `dashboard/.venv/` — dashboard backend (`dashboard/backend/requirements.txt`).
Frontend deps are in `dashboard/frontend/node_modules/`.

### Local config + DB (required before anything runs)
- `config.yml` is gitignored and must exist (copy from `config-example.yml`). Every service loads it at import and the seller-bot raises if `token` is missing.
- Create the DB schema once with the seller-bot's initializer (also seeds default tariffs/menus that the dashboard displays):
  `venv/bin/python -c "import asyncio; from app.database.models import async_main; asyncio.run(async_main())"`
  This writes `db.sqlite3` in the repo root (the seller bot uses a **relative** `db.sqlite3` path = cwd).

### Seller-bot cannot run/import without REAL payment + Telegram creds (external limitation)
- `main.py` → `app/handlers/payments.py` runs `@cp.invoice_paid()` at **import time**. `cp` is created in `app/settings.py` only when `crypto_bot_token` is set, and `aiosend.CryptoPay(...)` **validates the token via a live network call on construction**. Therefore:
  - empty `crypto_bot_token` → import fails with `NoneType has no attribute 'invoice_paid'`.
  - fake `crypto_bot_token` → import fails with a `[401] getMe UNAUTHORIZED`.
  - Running the seller-bot needs a **real CryptoBot API token** AND a **real Telegram bot token** (polling). These are not available in the cloud VM, so full seller-bot E2E is blocked here.
- The DB init above works because `crypto_bot_token` is left empty and only `app.database.models` is imported (not `app.handlers.payments`).
- support-bot imports fine with any correctly-formatted placeholder `support_token` (aiogram only checks token format at `Bot(...)`), but it still needs a real token to actually reach Telegram.

### Running the dashboard locally (fully works without external creds)
Backend (from `dashboard/`), pointing env vars at the repo-root config + DB (defaults point at container paths `/app/...`):
```
cd dashboard
CONFIG_PATH=/workspace/config.yml DB_PATH=/workspace/db.sqlite3 .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Frontend dev server (Vite, base `/bot/dashboard/`, proxies `/bot/dashboard/api` → `localhost:8000`):
```
cd dashboard/frontend && npm run dev -- --host 0.0.0.0
```
Open `http://localhost:5173/bot/dashboard/` and log in with `dashboard_login` / `dashboard_password` from `config.yml`. Changes made in the dashboard (tariffs/menus) are written to the shared `db.sqlite3` and picked up by the seller-bot via a version-polled cache (see `app/database/tariff_repository.py`).
