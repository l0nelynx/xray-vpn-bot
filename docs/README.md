# XRAY VPN Bot — Documentation

**Published:** [l0nelynx.github.io/xray-vpn-bot](https://l0nelynx.github.io/xray-vpn-bot/)

Telegram VPN subscription suite backed by **Remnawave**: seller bot, admin
Dashboard, Telegram MiniApp, browser [web portal](https://github.com/l0nelynx/web-portal),
and Android app — all on a shared PostgreSQL database.

!!! tip "Quick start"
    New to the project? Start with **[Deployment](deployment.md)** (Docker Compose,
    `config.yml`, networks) then skim **[Architecture](architecture.md)** for the
    big picture.

    The repository [README on GitHub](https://github.com/l0nelynx/xray-vpn-bot/blob/main/README.md)
    also has a copy-paste edge nginx config.

## Guides

| Topic | Description |
|-------|-------------|
| [Architecture](architecture.md) | Repo layout, containers, shared packages, networking |
| [Deployment](deployment.md) | Compose, images, migrations, CI, scaling notes |
| [Database](database.md) | `common_db`, schema, Alembic (HEAD `0014`) |
| [Integrations](integrations.md) | Remnawave webhooks, payment gateways, Telemt |

## Client APIs

| Topic | Description |
|-------|-------------|
| [Android API](android-api.md) | JWT auth, payments, IAP, support — full endpoint reference |
| [Web portal](web-portal.md) | External SPA repo, CORS, Telegram OIDC |
| [Connect page](connect-page.md) | `/connect-page` VPN app catalog override |

## Development

| Topic | Description |
|-------|-------------|
| [Promo refactor plan](promo-refactor-plan.md) | Referral system roadmap |
| [Promo system reference](claude.md) | Legacy promo map (contributor notes) |

## Local preview

```bash
pip install -r requirements-docs.txt
mkdocs serve   # http://127.0.0.1:8000
```
