# XRAY VPN Bot — Documentation

**Published:** [l0nelynx.github.io/xray-vpn-bot](https://l0nelynx.github.io/xray-vpn-bot/)

Telegram VPN subscription suite backed by **Remnawave**: seller bot, admin
Dashboard, Telegram MiniApp, browser [web portal](https://github.com/l0nelynx/web-portal),
and Android app — all on a shared PostgreSQL database.

!!! tip "New here?"
    1. Read **[Getting started → Overview](getting-started.md)** for prerequisites and the big picture.
    2. Follow **[Deployment](deployment.md)** to bring up Docker Compose.
    3. Fill in **[Configuration](configuration.md)** (`config.yml` + `.env`).
    4. Open the **[Dashboard](dashboard.md)** and build your tariff menu in **WebApp → Tariff Constructor**.

## Documentation map

### Getting started

| Guide | What you'll learn |
|-------|-------------------|
| [Overview](getting-started.md) | What the suite does, what you need before deploying |
| [Deployment](deployment.md) | Docker Compose, networks, reverse proxy, first boot |
| [Configuration](configuration.md) | Every `config.yml` key explained |
| [Local development](local-development.md) | Run services without Docker, MkDocs preview |

### Architecture & components

| Guide | What you'll learn |
|-------|-------------------|
| [Architecture](architecture.md) | Repo layout, containers, networking, data flow |
| [Seller bot](seller-bot.md) | Main Telegram bot, payment webhooks, admin bot |
| [Dashboard](dashboard.md) | Admin UI: tariffs, users, stats, support, Telemt |
| [MiniApp](miniapp.md) | Telegram WebApp: buy flow, subscription, support |
| [Web portal](web-portal.md) | External browser SPA, CORS, Telegram OIDC |
| [Android API](android-api.md) | JWT auth, Google Play IAP, account linking |

### Payments & operations

| Guide | What you'll learn |
|-------|-------------------|
| [Payment gateways](payment-gateways.md) | Built-in gateways + **how to add your own** |
| [Database](database.md) | `common_db`, schema, Alembic migrations |
| [Integrations](integrations.md) | Remnawave webhooks, Telemt monitoring |
| [Connect page](connect-page.md) | VPN app install catalog override |

## Quick reference

| Item | Value |
|------|-------|
| Dashboard URL | `https://your-domain/bot/dashboard/` |
| MiniApp URL | `https://your-domain/bot/miniapp/` |
| Dashboard API | `/bot/dashboard/api/` |
| MiniApp API | `/bot/miniapp/api/` |
| Payment webhooks | `/bot/*_webhook` → `bot:5000` |
| Config file | `config.yml` (copy from `config-example.yml`) |
| DB migrations | Alembic HEAD `0014_support_attachments` |

## Local preview

```bash
pip install -r requirements-docs.txt
mkdocs serve   # http://127.0.0.1:8000
```

The site is deployed automatically on push to `main` via `.github/workflows/docs.yml`
(GitHub Pages → Source: **GitHub Actions**).
