# Local development

This guide covers running services on your machine without the full production
stack, and previewing documentation changes.

## Documentation site (MkDocs)

```bash
pip install -r requirements-docs.txt
mkdocs serve   # docs only → http://127.0.0.1:8000

# Full Pages layout (landing at / + MkDocs at /docs/) — see docs/README.md
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Config: `mkdocs.yml`.

Production layout: landing at `/`, MkDocs at `/docs/` (see `landing/` and `docs/README.md`).
The site deploys automatically on push to `main` via `.github/workflows/docs.yml`.
First-time setup: repo **Settings → Pages → Source → GitHub Actions**.

## Frontend development

Dashboard and MiniApp are npm workspaces under `web/` (install from the **repo
root**: `npm install`).

### Mock API (no backend)

For UI work without Postgres / uvicorn / Telegram, start Vite in **mock mode**.
[MSW](https://mswjs.io/) intercepts `/bot/*/api/*` in the browser.

```bash
# Dashboard → http://127.0.0.1:5173/bot/dashboard/
npm run dev:mock -w xray-vpn-dashboard

# MiniApp → http://127.0.0.1:5174/bot/miniapp/  (second terminal)
npm run dev:mock -w xray-vpn-miniapp
```

- **Dashboard login:** any non-empty login/password (e.g. `admin` / `admin`).
- **MiniApp:** opens in a normal browser; Telegram initData is stubbed.
- **MiniApp UX scenarios:** append `?mock=<scenario>-<language>` to any route,
  for example `?mock=onboarding-ru`. Available scenarios include `onboarding`,
  `empty`, `single`, `multiple`, `connected`, `expired`, `connection-never`,
  `connection-progress`, and `connection-unknown`. Payment
  screens use transaction IDs `tx-awaiting`, `tx-processing`, `tx-failed`, and
  `tx-credits-1`; any other mock transaction progresses through all states.
- Handlers live in `web/apps/*/src/mocks/`. Unhandled API paths get a safe
  empty/`{ ok: true }` fallback so pages don't crash.
- Production builds do **not** enable mocks unless you pass
  `VITE_MOCK_API=1` at build time (don't).

### Dashboard (real API)

```bash
npm run dev -w xray-vpn-dashboard -- --host 0.0.0.0
```

Vite runs at `http://localhost:5173/bot/dashboard/` and proxies
`/bot/dashboard/api` → `http://localhost:8000`.

### MiniApp (real API)

```bash
npm run dev -w xray-vpn-miniapp -- --host 0.0.0.0
```

Dev server at `http://localhost:5173/bot/miniapp/`. Telegram init-data auth
requires opening the app inside Telegram when talking to a real backend.

### Production build

```bash
cd web
npm install
npm run build   # builds both SPAs into dist/
```

The `frontend` Docker image bakes these builds and serves them via nginx.

## Backend development (without Docker)

Each Python service has its own `requirements.txt` under `infra/docker/`. They
share packages from `packages/` (install in editable mode or via `PYTHONPATH`).

### PostgreSQL

Production uses PostgreSQL. For local dev you can either:

**Option A — Docker Postgres only:**

```bash
docker compose up -d postgres migrate
export DATABASE_URL="postgresql+asyncpg://xray:YOUR_PASSWORD@127.0.0.1:5432/xray_vpn_bot"
```

**Option B — SQLite fallback:**

Leave `DATABASE_URL` unset. The bot and miniapp fall back to `sqlite+aiosqlite`.

### Dashboard backend

```bash
cd services/dashboard
pip install -r ../../infra/docker/dashboard-requirements.txt
CONFIG_PATH=../../config.yml DATABASE_URL=... \
  uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

API at `http://localhost:8000/bot/dashboard/api/`.

### Miniapp backend

```bash
cd services/miniapp/backend
pip install -r ../../../infra/docker/miniapp-requirements.txt
CONFIG_PATH=../../config.yml DATABASE_URL=... \
  uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

API at `http://localhost:8001/bot/miniapp/api/`.

### Seller bot

!!! warning "CryptoBot import limitation"
    `services/bot/main.py` imports payment handlers at startup. If `crypto_bot_token`
    is set, `aiosend.CryptoPay` validates the token via a live API call on
    construction. A fake token causes import failure. For local bot development
    either use a real CryptoBot token or avoid importing payment modules.

```bash
cd services/bot
pip install -r ../../infra/docker/bot-requirements.txt
CONFIG_PATH=../../config.yml DATABASE_URL=... \
  python main.py
```

Webhooks listen on `:5000`. Telegram polling requires a real bot token.

### Database init / migrations

```bash
# Apply Alembic migrations
python -c "from migrations_runner import upgrade_to_head; upgrade_to_head()"

# Seed default tariffs/menus (first run)
python -c "import asyncio; from app.database.models import async_main; asyncio.run(async_main())"
```

Run from `services/bot/` with `DATABASE_URL` set.

### common_db drift tests

```bash
python -m pytest packages/common_db/tests -q
```

Live Postgres tests (`test_autogenerate_diff.py`) require `COMMON_DB_PG_URL`.

## Project structure for contributors

| Path | Role |
|------|------|
| `packages/common_db/` | Single ORM source of truth — add models here |
| `packages/payments/` | Payment gateway providers |
| `packages/remnawave_client/` | Remnawave API client |
| `alembic/versions/` | Database migrations |
| `services/bot/app/` | Bot handlers, payment webhooks |
| `services/dashboard/backend/routers/` | Dashboard API |
| `services/miniapp/backend/routers/` | MiniApp API |
| `web/apps/dashboard/src/pages/` | Dashboard UI pages |
| `web/apps/miniapp/src/pages/` | MiniApp UI pages |

### Adding a shared DB model

1. Model in `packages/common_db/common_db/models/`
2. Export from `models/__init__.py`
3. Alembic migration
4. Add to `CANONICAL_TABLES` in `packages/common_db/tests/test_alembic_target.py`
5. Re-export from service shims (dashboard, miniapp, bot)

See [database.md](database.md).

### Adding a payment gateway

See [payment-gateways.md](payment-gateways.md) — step-by-step guide.

## Docker Compose local debugging

Compose binds loopback ports for direct access:

| Service | Host port |
|---------|-----------|
| `bot` | `127.0.0.1:5000` |
| `dashboard` | `127.0.0.1:8080` → `:8000` |
| `miniapp` | `127.0.0.1:8001` |
| `frontend` | `127.0.0.1:8088` → `:80` |
| `postgres` | `127.0.0.1:5432` |

Build locally without pulling from ghcr:

```bash
# .env: REGISTRY=
docker compose --profile build build base
docker compose build
docker compose up -d
```
