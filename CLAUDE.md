# CLAUDE.md

Telegram VPN subscription suite backed by a **Remnawave** panel. Sells/manages VPN
plans via Telegram, with a web admin Dashboard, a Telegram MiniApp, a browser web
portal (separate frontend repo), and an Android app.

## Big picture

Several Python services share **one PostgreSQL database** and **one SQLAlchemy ORM**
(`packages/common_db`). Everything is orchestrated by `docker-compose.yml`.

Images are built by CI and published to GHCR: `:latest` (from `main`),
`:staging` (from `develop`), plus immutable `:sha-<short>` / `:build-<n>` tags.

## Docker services (docker-compose.yml)

Seven runtime services plus one-shot `migrate` and optional build-only `base`:

| Service | Image | Host port | Role |
|---|---|---|---|
| `postgres` | postgres:16-alpine | 127.0.0.1:5432 | Shared DB (`./pg_data`) |
| `migrate` | `bot` image | — | `alembic upgrade head`, then exits |
| `bot` | `ghcr.io/l0nelynx/bot` | 127.0.0.1:5000 | Main bot + payment webhooks (alias `seller-bot` on network) |
| `support-bot` | `support-bot` | — | Legacy SQLite support bot |
| `dashboard` | `dashboard` | 127.0.0.1:8080→8000 | FastAPI admin API |
| `miniapp` | `miniapp` | 127.0.0.1:8001 | FastAPI API (MiniApp / web portal / Android) |
| `frontend` | `frontend` | 127.0.0.1:8088→80 | nginx serving dashboard + miniapp SPAs |

App services depend on `migrate` completing. External networks:
`backend-network` (edge) and `mail-net` (SMTP for miniapp email). All backends
mount `config.yml` (read-only).

SSL terminates at the edge nginx — the bot container does **not** mount Marzban
cert volumes (legacy removed).

## Shared DB layer — `packages/common_db/`

**Single source of truth for the ORM.** Models live in
`packages/common_db/common_db/models/*.py`.

Service-side files are **shims that re-export, never re-declare**:
- `services/dashboard/backend/database/{models,url}.py`
- `services/miniapp/backend/database/{models,url}.py`
- `services/bot/app/database/models.py` — partial shim (keeps bot runtime:
  `engine`, `async_session`, `async_main()`, `_seed_*`)
- `services/bot/app/database/url.py`

**Adding a shared model:** model in `common_db/models/` → `models/__init__.py` →
Alembic migration → `CANONICAL_TABLES` in `test_alembic_target.py` → re-export
from all three shims.

**Drift guards** (`packages/common_db/tests/`):
`test_no_local_models.py`, `test_*_shim.py`, `test_alembic_target.py`,
`test_autogenerate_diff.py` (live PG, gated on `COMMON_DB_PG_URL`).
Run: `python -m pytest packages/common_db/tests -q`.

## Migrations — Alembic

`alembic/versions/` (`0001` → **`0021_referral_owner_points`**). Canon schema = HEAD.
`migrations_runner.upgrade_to_head()` runs in the `migrate` container and again
on miniapp/dashboard startup (no-op if already applied).

## Support bot is isolated (legacy)

`services/support_bot/support.py` — standalone aiogram bot on SQLite
(`db/support_bot.sqlite3`). Postgres table `support_users` has no `common_db`
model (`VESTIGIAL_TABLES`). Replacement ticketing lives in miniapp + dashboard;
retire `support.py` when ready.

## Component map

- **`services/bot/`** — Seller bot (`main.py`). `aiogram` 3.x + FastAPI webhooks.
  - `app/admin/` — admin bot (broadcasts, bans, logs, promos)
  - `app/api/` — payment gateways, Remnawave webhooks, Telemt
  - `app/handlers/`, `app/keyboards/`, `app/locale/`, `app/settings.py`
  - `app/bot_constructor/` — legacy in-bot menus (gated by `bot_feature_flags`)
- **`services/dashboard/backend/`** — FastAPI admin API at `/bot/dashboard/api`.
  Routers: users, transactions, stats, promos, crm, tariffs, menus, squads, telemt,
  store, support, webapp_*, tg_admin. `currency.py` converts amounts to RUB.
- **`web/apps/dashboard/`** — React 19 + shadcn/ui + Vite 8 admin SPA.
- **`services/miniapp/backend/`** — FastAPI at `/bot/miniapp/api`:
  - Telegram MiniApp (`tg_auth.py` init-data)
  - **Web portal API** (`web/web_router.py`) — used by external SPA
  - **Android API** (`android/`) — JWT, Google Play IAP, email verification
  - Invoice endpoints resolve price from `webapp_menu_nodes` by `node_id` only
- **`web/apps/miniapp/`** — Telegram MiniApp React SPA (React 19 + shadcn, in this repo).
- **`web/packages/ui/`** — shared `@xray/ui` shadcn components + dark CSS tokens.
- **[web-portal](https://github.com/l0nelynx/web-portal)** — browser web portal
  SPA (separate repo, deploy e.g. Vercel). Same stack mirrored locally; calls the
  same miniapp backend API.
- **`packages/`** — `common_db`, `remnawave_client`, `payments`,
  `account_linking`, `subscription_delivery`, `support_attachments`

## Config & secrets

Single `config.yml` (from `config-example.yml`), **gitignored**. Postgres creds
in `.env` (`POSTGRES_*`, `IMAGE_TAG`, optional `REGISTRY`).

| Key | Service | Notes |
|-----|---------|-------|
| `dashboard_secret` / `dashboard_password` | dashboard | Boot refuses insecure defaults |
| `android_jwt_secret` | miniapp | Boot refuses placeholder / short secret |
| `google_play_rtdn_token` | miniapp | Required when `google_play_package_name` set |
| `log_level` | miniapp | Default `normal` (= INFO); was env-only, now in config |
| `web_allowed_origins` | miniapp | CORS for external web portal |
| `tg_client_secret` | miniapp | Telegram OIDC for web portal login |

## Conventions / gotchas

- Dashboard tables paginate server-side — sort params go to the backend.
- Frontend UI: shadcn/ui + Tailwind 4; toasts via `sonner`; icons via `lucide-react`.
  Shared components live in `@xray/ui`. Dark theme is default (`class="dark"` on `<html>`).
- Payment currency mapping: `dashboard/backend/currency.py`.
- Frontend payment-method values must match DB names exactly.
- Shell is PowerShell on Windows — prefix commands or use absolute paths.
- **MiniApp / web / Android invoices** — client sends `node_id` only; never trust
  client `amount`/`days` (see `menu_invoice.py`, `android/payments_router.py`).
- Web portal BuyTab and MiniApp `BuyMenuPage.tsx` share tree-nav UX; both hit
  server-side menu nodes.
- `data-network` is **not** `internal: true` in compose (Postgres reachable on
  host loopback for ops). See `docs/deployment.md`.
- Frontend stack sync with the separate web portal: see `docs/frontend-stack.md`.

## Docs

Published site: **https://l0nelynx.github.io/xray-vpn-bot/** (landing + MkDocs at `/docs/`).

Local preview: `pip install -r requirements-docs.txt && mkdocs serve` (docs only), or assemble
landing + docs as in `docs/README.md`.

Source: [architecture](docs/architecture.md), [deployment](docs/deployment.md),
[database](docs/database.md), [crm](docs/crm.md), [referral](docs/referral.md),
[integrations](docs/integrations.md), [android-api](docs/android-api.md),
[web-portal](docs/web-portal.md), [connect-page](docs/connect-page.md).
