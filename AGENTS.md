# AGENTS.md

## Cursor Cloud specific instructions

Telegram VPN sales bot suite, restructured into a monorepo: Python services under `services/` (`bot`, `dashboard/backend`, `miniapp/backend`, `support_bot`), shared Python packages under `packages/`, React SPAs under `web/apps/` (npm workspaces), Alembic migrations under `alembic/`, and Dockerfiles under `infra/docker/`. Standard commands live in `README.md` and `docs/`; this section only captures the non-obvious, durable setup/run caveats for the cloud VM. The startup update script already installs all Python + npm deps — don't reinstall manually.

### Python env
- Single venv at `.venv/` (installed by the update script): shared base (`infra/docker/requirements-base.txt`) + all `packages/*` editable + the three service `requirements.txt` + `pytest`/`aiosqlite`. The base file is the single source of version truth; service files carry only extras.
- Benign install warning: `remnawave` pins `httpx<0.28` but the dashboard pulls `httpx 0.28.1`. In Docker they're separate images; in the single local venv httpx 0.28.1 wins. `remnawave` still imports and the full test suite passes, so this is safe for dev.

### Database = PostgreSQL (not SQLite)
- The Alembic migrations are **not** SQLite-compatible (`0007_fix_init_sizes` does Postgres-only `ALTER COLUMN ... TYPE BIGINT`), so local dev must use Postgres even though the code has a SQLite fallback for tests.
- Postgres 16 is installed as a system package. It is **not** auto-started (no systemd), so start it each session: `sudo pg_ctlcluster 16 main start`.
- Dev role/DB (already created; persists in the snapshot): role `xray` / password `xraydevpass`, database `xray_vpn_bot`. App connection string: `DATABASE_URL=postgresql+asyncpg://xray:xraydevpass@localhost:5432/xray_vpn_bot` (migrations_runner auto-converts asyncpg→psycopg2 for Alembic).
- Migrations auto-run on each backend's startup via `migrations_runner.upgrade_to_head()`. Default seed data (tariffs/menus/flags) is created **only** by the bot's `async_main()` — run it once after migrations if the dashboard shows no tariffs:
  `cd services/bot && PYTHONPATH=/workspace DATABASE_URL=... ../../.venv/bin/python -c "import asyncio; from app.database.models import async_main; asyncio.run(async_main())"`

### config.yml (gitignored) + symlinks
- `config.yml` lives at the repo root (copy of `config-example.yml`) and holds secrets; it persists in the snapshot.
- Boot-time security validation is strict: the dashboard refuses to start unless `dashboard_password` is set and not `"admin"`, and `dashboard_secret` is ≥32 bytes and not the built-in default; the miniapp requires `android_jwt_secret` ≥32 bytes and not the placeholder. Generate with `openssl rand -hex 32`.
- The bot and support bot load `config.yml` **relative to their own dir**, so both are symlinked to the root config: `services/bot/config.yml` and `services/support_bot/config.yml` → `../../config.yml`. These symlinks are required for `pytest` too (test collection imports `app.settings`, which `SystemExit`s if the bot config is missing).
- The support bot writes its own SQLite at `services/support_bot/db/support_bot.sqlite3`; ensure `services/support_bot/db/` exists before starting it.

### Running things (local dev; env vars go in the shell, not the update script)
- Tests: `cd /workspace && .venv/bin/python -m pytest -q` (in-memory SQLite; ~314 pass, 1 Postgres-only test skips unless `COMMON_DB_PG_URL` is set). No env/config needed beyond the bot config symlink.
- Dashboard API (`:8000`): `cd services/dashboard && CONFIG_PATH=/workspace/config.yml DATABASE_URL=... /workspace/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000` (set `EXPOSE_API_DOCS=1` for Swagger at `/bot/dashboard/api/docs`).
- Miniapp API (`:8001`): `cd services/miniapp && CONFIG_PATH=/workspace/config.yml DATABASE_URL=... /workspace/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8001`.
- Bot (`:5000` webhooks + polling): `cd services/bot && DATABASE_URL=... CONFIG_PATH=/workspace/config.yml PYTHONPATH=/workspace /workspace/.venv/bin/python main.py`.
- Frontends (npm workspaces, run from repo root): `npm run dev -w xray-vpn-dashboard -- --host 0.0.0.0 --port 5173` (SPA at `/bot/dashboard/`, proxies API to `:8000`) and `npm run dev -w xray-vpn-miniapp -- --host 0.0.0.0 --port 5174` (proxies to `:8001`). Build with `npm run build -w <name>`.

### Bot external limitation (not fixable in the VM)
The bot needs a **real CryptoBot token** (validated by a live network call at import) and a **real Telegram token**. Even then, `start_bot` (`services/bot/app/handlers/events.py`) messages `admin_id` on launch, so `admin_id` must be a real Telegram chat that has messaged the bot — otherwise startup crashes with `TelegramBadRequest: chat not found` (after successfully authenticating and starting polling). The subscription/purchase flow additionally needs a reachable Remnawave panel. Full interactive bot E2E is therefore blocked in the VM; the dashboard + miniapp + tests are the fully-runnable surface.
