# Web Portal

The browser-facing web portal is a **separate frontend repository** that talks to
the miniapp backend API in this monorepo.

- **Frontend repo:** [github.com/l0nelynx/web-portal](https://github.com/l0nelynx/web-portal)
- **Backend API:** `services/miniapp/backend/web/web_router.py` (mounted at
  `/bot/miniapp/api/web/…`)
- **Example deployment:** [web-portal-cheezy.vercel.app](https://web-portal-cheezy.vercel.app)

The Telegram MiniApp SPA (`web/apps/miniapp/`) lives in **this** repo and is
served by the `frontend` container. The web portal SPA is built and deployed
independently (e.g. Vercel Pages) and only needs network access to the miniapp
API on your domain.

## Architecture

```
┌─────────────────────┐         HTTPS CORS          ┌──────────────────────┐
│  web-portal (Vercel │  ─────────────────────────► │  miniapp :8001       │
│  or static host)    │   /bot/miniapp/api/web/…    │  web_router.py       │
└─────────────────────┘                             └──────────┬───────────┘
                                                               │
                                                    PostgreSQL + Remnawave
```

| Layer | Location | Role |
|-------|----------|------|
| SPA | [l0nelynx/web-portal](https://github.com/l0nelynx/web-portal) | Landing, login, register, dashboard (subscription, buy, devices, settings) |
| API | This repo → `miniapp` service | Auth, menu tree, invoices (`node_id`), devices, support |
| Static (optional) | `frontend` container at `/` | Can serve miniapp SPA; portal usually on its own host |

## Configuration (`config.yml`)

Keys read by `services/miniapp/backend/config.py`:

```yaml
# CORS — list every origin that hosts the portal SPA
web_allowed_origins:
  - https://your-portal.vercel.app
  - https://web.yourdomain.com

# Telegram "Sign in with Telegram" (OIDC Login 2.0)
tg_client_secret: "<from BotFather → Web Login → Client Secret>"

# Optional: separate chat for partnership form submissions
web_id: -1001234567890
```

**BotFather setup for Telegram login:**
1. `/mybots` → your bot → Bot Settings → Web Login → Set Domain → your portal domain
2. Copy Client Secret → `tg_client_secret` in `config.yml`
3. In the web-portal repo CI, set `VITE_TG_BOT_ID` to the bot's numeric ID

## API surface (summary)

All routes are under `/bot/miniapp/api/web/` (see `web_router.py` for the full
list). Highlights:

| Area | Endpoints |
|------|-----------|
| Auth | register (invite code), login, refresh, email verify, Telegram OIDC |
| Account | `/me`, settings |
| Buy | `/menu/tree`, `POST /payments/invoice` with **`node_id` only** |
| Devices | list, reset traffic |
| Support | tickets CRUD + attachments |
| Landing | partnership / feedback form |

Invoice creation matches Android/MiniApp security: the client sends only
`node_id`; price, days, provider and `tariff_slug` come from `webapp_menu_nodes`.

## Deployment checklist

1. Run the main stack (`docker compose up`) with `miniapp` reachable from the internet.
2. Set `web_allowed_origins` and `tg_client_secret` in `config.yml`; restart miniapp.
3. Build/deploy [web-portal](https://github.com/l0nelynx/web-portal) with API base
   URL pointing at `https://your-domain/bot/miniapp/api`.
4. Edge nginx must route `/bot/miniapp/api/` → `miniapp:8001` (see
   [edge nginx example](https://github.com/l0nelynx/xray-vpn-bot/blob/main/README.md#web-tier--reverse-proxy)).

## Local development

1. Start miniapp API locally or via compose (`127.0.0.1:8001`).
2. Clone web-portal, set `VITE_API_BASE` (or equivalent per that repo's `.env.example`)
   to `http://127.0.0.1:8001/bot/miniapp/api`.
3. Add `http://localhost:5173` (or your Vite port) to `web_allowed_origins`.

## Related docs

- [architecture.md](architecture.md) — how miniapp backs three clients
- [deployment.md](deployment.md) — CORS, networks, scaling notes
- [android-api.md](android-api.md) — parallel native client on the same backend
