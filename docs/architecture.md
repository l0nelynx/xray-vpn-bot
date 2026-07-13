# Architecture

XRAY-VPN-BOT is a suite for selling and managing VPN subscriptions through a
Telegram bot, an admin dashboard, a Telegram MiniApp, a browser web portal and an
Android app. Services run as Docker containers and share one PostgreSQL database.

## Repository layout

```
services/                     # deployable backends (one image each)
  bot/                        # main bot — aiogram + FastAPI payment webhooks
    app/                      #   python package (name kept as `app`)
    main.py
    scripts/
  support_bot/                # legacy support bot (own SQLite); to be retired
  dashboard/backend/          # FastAPI admin API
  miniapp/backend/            # FastAPI API for the MiniApp / web portal / Android
web/
  apps/dashboard/             # React + Vite SPA (admin)
  apps/miniapp/               # React + Vite SPA (Telegram MiniApp only)
  packages/ui/                # shared antd "liquid glass" theme builder (@xray/ui)
  packages/api/               # shared fetch client (@xray/api)
# Browser web portal SPA: https://github.com/l0nelynx/web-portal (separate repo)
packages/                     # shared python packages
  common_db/                  #   single SQLAlchemy Base + models + repo helpers
  remnawave_client/           #   Remnawave panel API client + subscription ops
  account_linking/            #   Android <-> Telegram account merge logic
  payments/                   #   gateway providers + webhook signature verification
  subscription_delivery/      #   Android paid-subscription delivery
infra/docker/                 # all Dockerfiles + the frontend nginx config
  base.Dockerfile             #   shared python base image (common deps)
  bot/support_bot/dashboard/miniapp.Dockerfile
  frontend.Dockerfile + frontend.nginx.conf
alembic/ alembic.ini migrations_runner.py   # shared DB migrations (repo root)
docker-compose.yml  package.json (npm workspaces root)  config.yml
```

## Containers

| Container | Image | Role |
|-----------|-------|------|
| `bot` | `bot` | Main Telegram bot + payment webhook endpoints (`:5000`). Keeps a `seller-bot` network alias. |
| `support-bot` | `support-bot` | Legacy standalone support bot, own SQLite. |
| `dashboard` | `dashboard` | Admin JSON API (`:8000`). |
| `miniapp` | `miniapp` | JSON API for MiniApp / web portal / Android (`:8001`). |
| `frontend` | `frontend` | nginx serving the two built SPAs as static files (`:80`). |
| `postgres` | `postgres:16` | Shared database. |
| `migrate` | `bot` image | One-shot Alembic `upgrade head`, then exits. |

Backends are **pure JSON APIs** — the SPAs are built once and served by the
`frontend` container, not by FastAPI. A `python-base` image (build-time only)
carries the common dependencies shared by `bot`/`dashboard`/`miniapp`.

### Bot
Customer-facing flows: browse plans, pay, check subscription status, get VLESS
links. In-Telegram admin actions: broadcasts, ban/unban, logs, scheduled DB
backups. Also runs the FastAPI server that receives payment-gateway webhooks
(`/bot/*_webhook`). Telegram polling is single-instance — the bot is **not**
horizontally scalable. Entry point: `services/bot/main.py`.

### Support bot
Standalone two-way user↔admin messaging (text/media) via an aiogram FSM "Answer"
flow. Uses its own SQLite under `./db/` — not on PostgreSQL. Legacy; will be
removed once ticketing in the MiniApp/Dashboard fully replaces it.

### Dashboard
Admin web UI (no DB/code access needed): tariff constructor, dynamic menu
builder, users, transactions & stats, promo codes, Telemt server control. JWT
auth from `dashboard_login` / `dashboard_password`, tokens signed with
`dashboard_secret`. Backend is API-only; the SPA is served by `frontend`.

### MiniApp, web portal & Android API
One FastAPI service (`miniapp`) backs three clients, all under `/bot/miniapp/api/`:
- **Telegram MiniApp** — TWA authenticated by Telegram init-data; SPA in
  `web/apps/miniapp/` (this repo).
- **Web portal** — browser client in the separate
  [web-portal](https://github.com/l0nelynx/web-portal) repo (invite + email/password
  or Telegram OIDC). API: `web/web_router.py`. See [web-portal.md](web-portal.md).
- **Android app** — JWT-authenticated native client, incl. Google Play IAP.
  See [android-api.md](android-api.md).

All payment invoice endpoints accept **`node_id` only** — tariff price/days are
read from `webapp_menu_nodes`, never from the client.

### Frontend
nginx image that bakes in both built SPAs (`web/apps/*`) and serves them as
static files. It does **no** proxying — all routing is owned by the edge nginx.

## Shared code

Cross-service logic lives in `packages/` (python) and `web/packages/` (frontend),
defined once and consumed by every service:

- `common_db` owns the single `Base.metadata` (Alembic autogenerates against it),
  the ORM models and `repo/*` query helpers.
- `remnawave_client` and `payments` are credential-free; each service injects its
  config via `set_config_provider` at startup.
- `account_linking` / `subscription_delivery` hold the Android merge and paid
  delivery logic shared by the bot and the miniapp.

## Data flow

- Users interact with the Bot, MiniApp or web portal; the Android app calls the
  MiniApp API.
- All backends share one **PostgreSQL** database (`DATABASE_URL`).
- VPN provisioning goes through the **Remnawave** panel via `remnawave_client`.
- Payments: gateways (CryptoBot, CrystalPay, Platega, APay, ParityPay) and
  Google Play IAP create invoices via `packages/payments`; confirmations hit the
  bot's webhook endpoints, which verify signatures (`payments.signatures`) and
  deliver the subscription.

## Networking

Two Docker networks (see [deployment.md](deployment.md)):

- **backend-network** (external) — the edge; reverse-proxy nginx, app backends
  and `frontend` live here.
- **data-network** — PostgreSQL and DB-connected backends. Postgres is **not**
  on `backend-network`, so it is not reachable from the edge nginx. The network
  is **not** marked `internal: true` in compose so Postgres remains reachable on
  the host bind (`127.0.0.1:5432`) for backups and local tools.

## Web tier & reverse proxy

The edge nginx terminates TLS and routes by URL prefix (every API path is under
`.../api`, so the static-vs-API split is unambiguous):

| Path | Target |
|------|--------|
| `/bot/dashboard/api/…` | `dashboard:8000` |
| `/bot/dashboard/…` | `frontend:80` (dashboard SPA) |
| `/bot/miniapp/api/…` | `miniapp:8001` |
| `/bot/miniapp/…` | `frontend:80` (miniapp SPA) |
| `/bot/…` | `bot:5000` (payment webhooks) |
| `/` | `frontend:80` or external web portal host |

The ready-to-use edge nginx config (with the Docker-DNS resolver pattern that
avoids startup failures) is in the project [README](../README.md).
