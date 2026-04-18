# Telegram VPN Sales Bot

Advanced Telegram bot suite for selling VPN subscriptions, backed by **Remnawave** and driven through a web **Dashboard** with a built-in tariff/menu builder.

## Features
- 🔐 Sell VPN subscriptions via Telegram
- 💳 Multiple payment gateways (CryptoBot, Crystal Pay, A-Pays)
- 🌐 Remnawave VPN API integration (internal + external squads)
- 🧩 Web Dashboard with tariff constructor and menu builder
- 🛰️ Telemt server management from the Dashboard
- 💬 Dedicated support bot
- 🛠️ Admin bot for broadcasts, moderation and logs
- 📊 SQLite storage with async SQLAlchemy
- 🚀 FastAPI webhook endpoints for payments
- 🐳 Docker Compose deployment (seller-bot + support-bot + dashboard)
- 🔄 Async aiogram 3.x architecture

## Architecture

The project ships three containers orchestrated by `docker-compose.yml`:

| Service | Image | Purpose |
|---------|-------|---------|
| `seller-bot` | `ghcr.io/l0nelynx/seller-bot` | Main user-facing Telegram bot + payment webhooks (port `5000`) |
| `support-bot` | `ghcr.io/l0nelynx/support-bot` | Standalone bot for user↔admin conversations |
| `dashboard` | `ghcr.io/l0nelynx/dashboard` | React + FastAPI admin panel (port `8000`, mapped to `8080` on host) |

Images are built by CI (`.github/workflows/build.yml` and `.gitlab-ci.yml`) and published as:
- `:latest` — built from `main`
- `:staging` — built from `develop`
- `:sha-<short>` / `:build-<n>` — immutable per-build tags

## Dashboard

The Dashboard is a web app bundled with the project (`dashboard/`) that turns configuration into a UI workflow:

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

### 2. Prepare the database

```bash
mkdir -p db
touch db/db.sqlite3
```

### 3. Prepare the shared Docker network

The compose file expects an external network named `backend-network` (typical when running behind a reverse proxy). Create it once:

```bash
docker network create backend-network
```

### 4. Launch

Pull the published images and start everything:

```bash
docker compose pull
docker compose up -d
```

Or build locally from source:

```bash
docker compose build
docker compose up -d
```

Services:
- Seller bot webhooks: `127.0.0.1:5000`
- Dashboard: `127.0.0.1:8080` (FastAPI listens on `:8000` inside the container)

Put a reverse proxy (nginx / Caddy / Traefik) in front to terminate TLS and expose the Dashboard at `/bot/dashboard` and the payment webhook endpoints on your public domain.

### Running locally (without Docker)

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

pip install -r requirements.txt
python main.py &
python support.py &
wait
```

The Dashboard has its own stack (`dashboard/backend` + `dashboard/frontend`); see `dashboard/Dockerfile` for the reference build.

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
| `dashboard_secret` | JWT signing secret |

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
├── app/                          # Seller bot application code
│   ├── admin/                    # Admin bot (broadcasts, bans, logs, migrations, ...)
│   ├── api/                      # Payment gateway + Remnawave + Telemt clients
│   │   ├── a_pay.py
│   │   ├── crystal_pay.py
│   │   ├── remnawave/
│   │   └── telemt.py
│   ├── database/                 # Async SQLAlchemy models & queries
│   ├── handlers/                 # Bot command and callback handlers
│   ├── keyboards/                # Inline/reply keyboards
│   ├── locale/                   # Russian + English locale files
│   ├── marzban/                  # (legacy) kept for migration purposes
│   ├── settings.py               # Config loader + bot/uvicorn bootstrap
│   └── tariffs.py                # Runtime tariff helpers
├── dashboard/                    # Admin dashboard (React + FastAPI)
│   ├── backend/                  # FastAPI app, routers, JWT auth
│   ├── frontend/                 # React + Vite SPA
│   └── Dockerfile
├── db/                           # SQLite storage (mounted into containers)
├── uvicorn/                      # Optional SSL artifacts
├── main.py                       # Seller bot entry point
├── support.py                    # Support bot entry point
├── Dockerfile                    # Seller bot image
├── Dockerfile_support            # Support bot image
├── docker-compose.yml            # Full stack orchestration
├── config-example.yml            # Example configuration
├── config.yml                    # Your configuration (gitignored)
├── requirements.txt              # Seller bot deps
├── requirements_support.txt      # Support bot deps
└── .github/workflows/build.yml   # CI: build & push to GHCR
```

## Dependencies

Core:
- **aiogram** 3.21+ — async Telegram framework
- **FastAPI** 0.116+ — webhook endpoints + Dashboard API
- **SQLAlchemy** 2.0+ / **aiosqlite** — async ORM on SQLite
- **uvicorn** / **slowapi** — ASGI server + rate limiting

HTTP / data:
- **aiohttp**, **requests**, **httpx** — HTTP clients
- **aiosend** — CryptoBot wrapper
- **orjson**, **PyYAML**, **pydantic** — (de)serialization + validation

VPN integration:
- **remnawave** 2.1+ — Remnawave API SDK

## Troubleshooting

**`config file not found`** — the container must mount `config.yml` at `/usr/src/app/config.yml` (seller/support) or `/app/config.yml` (dashboard). Check the `volumes:` in `docker-compose.yml`.

**`'token' is not set in config.yml`** — `config.yml` is loaded but missing the main bot token. Compare against `config-example.yml`.

**Payment webhooks not firing** — verify your reverse proxy forwards to port `5000` of the seller-bot container, and that `crystal_webhook` / A-Pays callback URLs point to the public domain (HTTPS).

**Remnawave connection failed** — verify `remnawave_url` includes `https://`, the API token is valid, and the squad UUIDs (`rw_free_id`, `rw_pro_id`, `rw_ext_*`) exist in the panel.

**Dashboard 401 on login** — `dashboard_login` / `dashboard_password` must match what you enter in the UI; rotating `dashboard_secret` invalidates existing sessions.

**Telemt calls return 503** — `telemt_server` is empty or unreachable. Fill it in (and `telemt_header`) if you want host management from the Dashboard.

## License
MIT License — see [LICENSE](LICENSE).

## Support
Open an issue on GitHub for bugs and feature requests.

---
**Made with ❤️ for the VPN community**
