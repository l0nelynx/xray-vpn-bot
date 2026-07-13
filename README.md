# Telegram VPN Sales Bot

Advanced Telegram bot suite for selling VPN subscriptions, backed by **Remnawave** and driven through a web **Dashboard** with a built-in tariff/menu builder.

## Features
- 🔐 Sell VPN subscriptions via Telegram MiniApp and browser web portal
- 💳 Multiple payment gateways (CryptoBot, Crystal Pay, A-Pays, Platega, ParityPay)
- 🌐 Remnawave VPN API integration (internal + external squads)
- 🧩 Web Dashboard with tariff constructor and menu builder
- 📱 Android app API + Google Play IAP
- 🛰️ Telemt server management from the Dashboard
- 💬 In-app support tickets (legacy standalone support bot optional)
- 🛠️ Admin bot for broadcasts, moderation and logs
- 📊 PostgreSQL storage with shared SQLAlchemy ORM (`common_db`)
- 🚀 FastAPI webhook endpoints for payments
- 🐳 Docker Compose deployment (bot + dashboard + miniapp + frontend + postgres)
- 🔄 Async aiogram 3.x architecture

## Architecture

Services live under `services/`, shared Python packages under `packages/`, the
frontends and their shared packages under `web/`, and all Dockerfiles under
`infra/docker/`. `docker-compose.yml` orchestrates these containers:

| Service | Image | Purpose |
|---------|-------|---------|
| `bot` | `ghcr.io/l0nelynx/bot` | Main user-facing Telegram bot + payment webhooks (port `5000`). Keeps a `seller-bot` network alias for backwards compatibility. |
| `support-bot` | `ghcr.io/l0nelynx/support-bot` | Legacy standalone bot for user↔admin conversations (own SQLite). |
| `dashboard` | `ghcr.io/l0nelynx/dashboard` | FastAPI admin **API** (port `8000`). |
| `miniapp` | `ghcr.io/l0nelynx/miniapp` | FastAPI **API** for MiniApp / web portal / Android (`8001`). |
| `frontend` | `ghcr.io/l0nelynx/frontend` | nginx serving dashboard + miniapp SPAs (`80`). |
| `postgres` / `migrate` | `postgres:16` / `bot` image | Shared database and one-shot Alembic migrations. |
| `python-base` | `ghcr.io/l0nelynx/python-base` | Build-time base image: common Python deps + `common_db`/`remnawave_client`, shared by `bot`/`dashboard`/`miniapp` (not a runtime service). |

The backends are **pure JSON APIs** — the dashboard and Telegram MiniApp SPAs are
built in this repo and served by the `frontend` container. The **browser web
portal** frontend lives in a [separate repository](https://github.com/l0nelynx/web-portal)
and calls the same miniapp API (see [docs/web-portal.md](docs/web-portal.md)).

Images are built by CI (`.github/workflows/build.yml` and `.gitlab-ci.yml`) and published as:
- `:latest` — built from `main`
- `:staging` — built from `develop`
- `:sha-<short>` / `:build-<n>` — immutable per-build tags

**Documentation site:** [l0nelynx.github.io/xray-vpn-bot](https://l0nelynx.github.io/xray-vpn-bot/)
(built from `docs/` via MkDocs on push to `main`).

### Web tier & reverse proxy

Routing is owned by the **edge nginx**. The `frontend` container
(`infra/docker/frontend.Dockerfile` + `infra/docker/frontend.nginx.conf`) only
serves the two built SPAs as static files; the backends are pure JSON APIs. The
edge routes by URL prefix — every API endpoint lives under `.../api`, so the
static-vs-API split is unambiguous:

| Path | Target |
|------|--------|
| `/bot/dashboard/api/…` | `dashboard:8000` (admin API) |
| `/bot/dashboard/…` | `frontend:80` (dashboard SPA) |
| `/bot/miniapp/api/…` | `miniapp:8001` (miniapp / web portal / android API) |
| `/bot/miniapp/…` | `frontend:80` (miniapp SPA) |
| `/bot/…` | `bot:5000` (payment webhooks, e.g. `/bot/apays_webhook`) |
| `/` | `frontend:80` (miniapp SPA — public web portal entry) |

The edge nginx must share the `backend-network` so the container names resolve.

> **Important:** do NOT use `upstream { server dashboard:8000; }` blocks (or a
> bare `proxy_pass http://dashboard:8000;`). nginx resolves those names **at
> startup** and aborts with `[emerg] host not found in upstream` if a backend
> isn't running/resolvable yet. Instead, use Docker's embedded DNS resolver
> (`127.0.0.11`) and put the target in a **variable** — that defers resolution
> to request time. With a variable you must append `$request_uri` to preserve
> the path (and the backend receives the original `/bot/<app>/…` URI unchanged).

```nginx
server {
    listen 443 ssl;
    server_name example.com;
    # ... ssl_certificate / ssl_certificate_key ...

    # Support-ticket image attachments (up to 3 images/message) can exceed
    # nginx's 1MB default — without this, uploads silently 413 before they
    # reach the containers.
    client_max_body_size 20m;

    # Docker's embedded DNS — required for the runtime resolution below.
    resolver 127.0.0.11 valid=30s ipv6=off;

    # Shared proxy headers.
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # APIs — longest-prefix match wins, so these beat the SPA blocks below.
    location /bot/dashboard/api/ {
        set $up dashboard:8000;
        proxy_pass http://$up$request_uri;
    }
    location /bot/miniapp/api/ {
        set $up miniapp:8001;
        proxy_pass http://$up$request_uri;
    }

    # SPAs (static) -> frontend container.
    location /bot/dashboard/ {
        set $up frontend:80;
        proxy_pass http://$up$request_uri;
    }
    location /bot/miniapp/ {
        set $up frontend:80;
        proxy_pass http://$up$request_uri;
    }

    # Payment webhooks and other bot endpoints.
    location /bot/ {
        set $up bot:5000;
        proxy_pass http://$up$request_uri;
    }

    # Public entry — miniapp SPA and/or external web portal host.
    location / {
        set $up frontend:80;
        proxy_pass http://$up$request_uri;
    }
}
```

## Dashboard

The Dashboard is the admin SPA (`web/apps/dashboard/`) backed by
`services/dashboard/backend/`:

- **Tariff constructor** — create, reorder, price and toggle subscription plans without touching code. Changes propagate to the bot automatically.
- **Menu builder** — design the bot's inline menus (screens, buttons, links) and edit them live.
- **Users & transactions** — browse customers, subscriptions and payment history.
- **Promos** — manage promo codes and bonus settings.
- **Squad profiles** — bind Remnawave squads to plans.
- **Telemt control** — view system info/health of the external Telemt server and manage host/server state directly from the Dashboard.
- **Stats** — traffic and revenue dashboards.

The Dashboard authenticates via `dashboard_login` / `dashboard_password` from `config.yml` and issues JWTs signed with `dashboard_secret`. It is mounted at `/bot/dashboard` (expose it behind a reverse proxy).

## Quick Start

### Prerequisites
- Docker & Docker Compose
- A running Remnawave panel with an API token
- Telegram bot tokens (main bot, support bot, admin bot)
- (Optional) Payment gateway credentials
- (Optional) Telemt server if you want host management from the Dashboard

### 1. Configure

```bash
cp config-example.yml config.yml
# then edit config.yml
```

Fill in at minimum:

```yaml
branding_name: "YourVPN"
token: "<main bot token>"
support_token: "<support bot token>"
admin_bot_token: "<admin bot token>"
admin_id: 123456789

remnawave_url: "https://panel.example.com"
remnawave_token: "<remnawave api token>"
rw_free_id: "<free squad uuid>"
rw_pro_id: "<pro squad uuid>"
rw_ext_free_id: "<external free squad uuid>"
rw_ext_pro_id: "<external pro squad uuid>"

dashboard_login: admin
dashboard_password: <strong password>
dashboard_secret: <random string>
```

> ⚠️ Add `config.yml` to `.gitignore` — it contains secrets.

### 2. Environment

```bash
cp .env.example .env
# set POSTGRES_PASSWORD (required)
```

### 3. Prepare Docker networks

```bash
docker network create backend-network
docker network create mail-net
```

### 4. Launch

Pull the published images and start everything:

```bash
docker compose pull
docker compose up -d
```

Or build locally from source. The three Python backends (`bot`, `dashboard`,
`miniapp`) share a base image with the common, heavy dependencies — build it
first, then the services:

```bash
docker compose --profile build build base   # shared Python base (deps once)
docker compose build                         # bot / dashboard / miniapp / frontend
docker compose up -d
```

> The shared base (`infra/docker/base.Dockerfile` + `requirements-base.txt`)
> carries fastapi/uvicorn/sqlalchemy/pydantic/asyncpg/psycopg2/alembic plus
> `common_db` and `remnawave_client`, so those are built and stored once instead
> of per service. In CI the `python-base` image is rebuilt **only when its own
> inputs change** (base.Dockerfile, requirements-base.txt, common_db,
> remnawave_client); service-only changes reuse the already-published base.

Services:
- Bot webhooks: `127.0.0.1:5000`
- Dashboard API: `127.0.0.1:8080` (FastAPI listens on `:8000` inside the container)
- Miniapp API: `127.0.0.1:8001`
- Web SPAs: `127.0.0.1:8088` (frontend container)
- Postgres: `127.0.0.1:5432`

Put a reverse proxy (nginx / Caddy / Traefik) in front to terminate TLS and expose the Dashboard at `/bot/dashboard` and the payment webhook endpoints on your public domain.

### Running locally (without Docker)

See `services/bot/main.py`, `services/support_bot/support.py`, and per-service
`requirements.txt` files under `infra/docker/`. Postgres (or SQLite fallback
without `DATABASE_URL`) is required for the main bot and miniapp.

## Configuration Reference

### Main

| Parameter | Description |
|-----------|-------------|
| `branding_name` | Service name shown to users |
| `support_bot_id` | Support bot `@username` mention |
| `news_url` | Public news/announcements channel link |
| `agreement_url`, `policy_url` | User agreement and privacy policy URLs |
| `uvicorn_host`, `uvicorn_port` | Webhook server bind address/port |

### Bots

| Parameter | Description |
|-----------|-------------|
| `token` | Main Telegram bot token |
| `support_token` | Support bot token |
| `admin_bot_token` | Admin bot token (admin panel + broadcasts) |
| `admin_id` | Admin Telegram user ID |
| `news_id` | Numeric ID of the news channel (for broadcasts) |

### Remnawave

| Parameter | Description |
|-----------|-------------|
| `remnawave_url` | Remnawave panel URL |
| `remnawave_token` | Remnawave API token |
| `rw_free_id` / `rw_pro_id` | Internal squad IDs for FREE / PRO users |
| `rw_ext_free_id` / `rw_ext_pro_id` | External squad IDs (extended-access variants) |

### Dashboard

| Parameter | Description |
|-----------|-------------|
| `dashboard_login` | Dashboard admin login |
| `dashboard_password` | Dashboard admin password |
| `dashboard_secret` | JWT signing secret (≥32 bytes; boot refuses weak defaults) |
| `android_jwt_secret` | Miniapp/Android/web JWT secret (≥32 bytes; boot refuses placeholder) |
| `log_level` | Miniapp logging: `normal` (default), `debug`, `warning`, `error` |

### Telemt

| Parameter | Description |
|-----------|-------------|
| `telemt_server` | Telemt API base URL |
| `telemt_header` | Authorization header value forwarded to Telemt |

### Promo / Admin

| Parameter | Description |
|-----------|-------------|
| `promo_discount` | Promo code discount in % |
| `promo_days_reward` | Promo code extra days reward |
| `admin_logs_length` | Rows shown in the admin logs panel |

### Payment Gateways

| Parameter | Description |
|-----------|-------------|
| `crypto_bot_token` | CryptoBot API token |
| `crystal_login` / `crystal_secret` / `crystal_salt` / `crystal_webhook` | Crystal Pay credentials + webhook URL |
| `apay_id` / `apay_secret` / `apay_api_url` | A-Pays merchant ID, secret, API URL |

### Seed prices

These values seed defaults on first launch only — after that, manage tariffs through the Dashboard's tariff constructor:

| Parameter | Description |
|-----------|-------------|
| `stars_price` | 1-month base price in Telegram Stars |
| `crypto_price` | 1-month base price in USDT |
| `sbp_price` | 1-month base price in RUB (SBP) |
| `discount` | Base discount (%) for plans of 3+ months |
| `free_traffic` | FREE plan traffic limit (GB) |
| `free_days` | FREE plan duration (days) |

## Project Structure

```
.
├── services/
│   ├── bot/                    # Main Telegram bot + payment webhooks
│   ├── dashboard/backend/      # FastAPI admin API
│   ├── miniapp/backend/        # MiniApp / web portal / Android API
│   └── support_bot/            # Legacy support bot (SQLite)
├── web/
│   ├── apps/dashboard/         # Admin React SPA
│   ├── apps/miniapp/           # Telegram MiniApp React SPA
│   └── packages/               # Shared frontend packages (@xray/ui, @xray/api)
├── packages/                   # Shared Python packages (common_db, payments, …)
├── infra/docker/               # Dockerfiles + frontend nginx config
├── alembic/                    # Database migrations
├── docker-compose.yml
├── config-example.yml
└── config.yml                  # Your secrets (gitignored)
```

Browser web portal SPA: [github.com/l0nelynx/web-portal](https://github.com/l0nelynx/web-portal)
(separate repo).

## Dependencies

Core:
- **aiogram** 3.x — async Telegram framework
- **FastAPI** — webhook endpoints + admin/miniapp APIs
- **SQLAlchemy** 2.0+ / **asyncpg** — async ORM on PostgreSQL
- **uvicorn** / **slowapi** — ASGI server + rate limiting

HTTP / data:
- **aiohttp**, **requests**, **httpx** — HTTP clients
- **aiosend** — CryptoBot wrapper
- **orjson**, **PyYAML**, **pydantic** — (de)serialization + validation

VPN integration:
- **remnawave** 2.1+ — Remnawave API SDK

## Troubleshooting

**`config file not found`** — mount `config.yml` at `/usr/src/app/config.yml` (bot)
or `/app/config.yml` (dashboard/miniapp). Check `volumes:` in `docker-compose.yml`.

**`android_jwt_secret` / `dashboard_secret` boot error** — generate with
`openssl rand -hex 32` and replace placeholder values in `config.yml`.

**Payment webhooks not firing** — verify your reverse proxy forwards `/bot/*` to
port `5000` of the `bot` container, and that gateway callback URLs use HTTPS.

**Remnawave connection failed** — verify `remnawave_url` includes `https://`, the API token is valid, and the squad UUIDs (`rw_free_id`, `rw_pro_id`, `rw_ext_*`) exist in the panel.

**Dashboard 401 on login** — `dashboard_login` / `dashboard_password` must match what you enter in the UI; rotating `dashboard_secret` invalidates existing sessions.

**Telemt calls return 503** — `telemt_server` is empty or unreachable. Fill it in (and `telemt_header`) if you want host management from the Dashboard.

## License
MIT License — see [LICENSE](LICENSE).

## Support
Open an issue on GitHub for bugs and feature requests.

---
**Made with ❤️ for the VPN community**
