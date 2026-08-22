# XRAY VPN Bot — Documentation

**Project site:** [l0nelynx.github.io/xray-vpn-bot](https://l0nelynx.github.io/xray-vpn-bot/)  
**This documentation:** [l0nelynx.github.io/xray-vpn-bot/docs](https://l0nelynx.github.io/xray-vpn-bot/docs/)

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
| [Architecture](architecture.md) | Repo layout, containers, shared packages, networking |
| [Seller bot](seller-bot.md) | Main Telegram bot, payment webhooks, admin bot |
| [Dashboard](dashboard.md) | Admin UI: tariffs, users, stats, CRM, support |
| [MiniApp](miniapp.md) | Telegram WebApp: buy flow, subscription, support |
| [Web portal](web-portal.md) | External browser SPA, CORS, Telegram OIDC |
| [Android API](android-api.md) | JWT auth, Google Play IAP, account linking |

### Growth

| Guide | What you'll learn |
|-------|-------------------|
| [CRM](crm.md) | Segments, campaigns, scheduled events, perks |
| [Referral & promocodes](referral.md) | Bonus credits wallet, referral rewards, admin settings |

### Payments & operations

| Guide | What you'll learn |
|-------|-------------------|
| [Payment gateways](payment-gateways.md) | Built-in gateways + **how to add your own** |
| [Database](database.md) | `common_db`, schema, Alembic migrations |
| [Integrations](integrations.md) | Remnawave webhooks, Telemt monitoring |
| [Remnawave v3 rollout](remnawave-v3-rollout.md) | Safe panel/API v3 maintenance window and smoke tests |
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
| DB migrations | Alembic HEAD `0021_referral_owner_points` |

## Local preview

```bash
# MkDocs only (docs live under /docs/ in production)
pip install -r requirements-docs.txt
mkdocs serve   # http://127.0.0.1:8000

# Full GitHub Pages layout (landing + /docs)
mkdocs build --strict --site-dir site/docs
cp landing/index.html landing/styles.css landing/carousel.js landing/stats.js site/
mkdir -p site/assets/screenshots && cp docs/screenshots/*.png site/assets/screenshots/
python -m http.server -d site 8080   # http://127.0.0.1:8080/
```

The site is deployed automatically on push to `main` via `.github/workflows/docs.yml`
(GitHub Pages → Source: **GitHub Actions**). Landing is the site root; MkDocs is
published at `/docs/`.
