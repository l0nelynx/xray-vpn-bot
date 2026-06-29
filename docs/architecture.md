# Project Architecture

XRAY-VPN-BOT is a suite for selling and managing VPN subscriptions via Telegram,
an admin dashboard and a Telegram MiniApp / Android app. Services are orchestrated
with Docker Compose and share a single PostgreSQL database.

## Repository layout

```
services/                 # deployable services (one image each)
  bot/                    # main seller bot — aiogram + FastAPI webhooks
    app/                  #   python package (kept name `app`)
    main.py
    scripts/
  support_bot/            # legacy support bot (own SQLite); to be retired
  dashboard/backend/      # FastAPI admin API
  miniapp/backend/        # FastAPI API for the MiniApp / web portal / Android
web/
  apps/dashboard/         # React + Vite (admin)
  apps/miniapp/           # React + Vite (MiniApp)
  packages/ui/            # shared antd liquid-glass theme builder (@xray/ui)
  packages/api/           # shared fetch client (@xray/api)
packages/                 # shared python packages (installed into each image)
  common_db/              #   single SQLAlchemy Base + models + repo helpers
  remnawave_client/       #   Remnawave panel API client + subscription ops
  account_linking/        #   Android<->Telegram account merge logic
  payments/               #   gateway providers + webhook signature verification
  subscription_delivery/  #   Android paid-subscription delivery
infra/docker/             # bot / support_bot / dashboard / miniapp Dockerfiles
alembic/ alembic.ini migrations_runner.py   # shared DB migrations (root)
docker-compose.yml  package.json (npm workspaces root)  config.yml
```

## Components

1. **Bot** (`services/bot`, image `bot`) — customer-facing Telegram bot: plan
   selection, payments, subscription management. Hosts the payment webhook
   endpoints (`/bot/*_webhook`). Tech: aiogram 3.x, FastAPI, SQLAlchemy.
2. **Support bot** (`services/support_bot`) — legacy ticket/DM bot with its own
   SQLite DB. Slated for removal once tickets land in miniapp/dashboard.
3. **Dashboard** (`services/dashboard/backend` + `web/apps/dashboard`) — admin
   web UI: tariffs, menus, users, stats. FastAPI + JWT; React/Vite/antd frontend.
4. **MiniApp** (`services/miniapp/backend` + `web/apps/miniapp`) — Telegram
   MiniApp + web portal + Android API (JWT, Google Play IAP). FastAPI; React/Vite.

## Shared code

Cross-service logic lives in `packages/` (python) and `web/packages/` (frontend)
so it is defined once and consumed by every service. Notably `common_db` owns the
single `Base.metadata` (alembic autogenerates against it), and each service wires
credentials into `remnawave_client` / `payments` via `set_config_provider`.

## Data flow

- Users interact with the Bot or MiniApp; the Android app talks to the MiniApp API.
- All services share one **PostgreSQL** database (`DATABASE_URL`), so state is
  consistent across bot, dashboard and miniapp.
- VPN provisioning goes through the **Remnawave** panel via `remnawave_client`.
- Payments: external gateways (CryptoBot, CrystalPay, Platega, APay) and Google
  Play IAP create invoices via `packages/payments`; confirmations hit the bot's
  webhook endpoints, which verify signatures (`payments.signatures`) and deliver.

## Deployment & networking

`docker-compose.yml` defines: `postgres`, `migrate` (one-shot alembic), `bot`,
`support-bot`, `dashboard`, `miniapp`. Networks are segmented:

- **backend-network** (external) — the edge; nginx is attached here and proxies
  to the app backends. The `bot` service keeps a `seller-bot` network alias for
  backwards compatibility with the existing nginx upstream.
- **data-network** (internal, no gateway) — PostgreSQL + the services that talk
  to it. Postgres is not reachable from the edge.

Frontends are built (npm workspaces) and their `dist` is served as static files
by the corresponding FastAPI service, fronted by nginx.
