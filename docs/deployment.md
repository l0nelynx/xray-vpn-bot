# Deployment

Containerised deployment via Docker Compose. See [architecture.md](architecture.md)
for the container list and networking model.

## Prerequisites

- Docker + Docker Compose.
- A Telegram bot token (and optionally separate admin/support tokens).
- A Remnawave URL + API token.
- (Optional) payment-gateway credentials.
- External Docker networks (create once):

```bash
docker network create backend-network   # edge — shared with reverse-proxy nginx
docker network create mail-net          # SMTP egress for miniapp email verification
```

## Configuration

### `config.yml`
Application config (tokens, Remnawave, dashboard creds, payment keys, branding):

```bash
cp config-example.yml config.yml   # then edit
```

Mounted read-only into `bot`, `dashboard`, `miniapp`; read-write for `support-bot`
(legacy). Key groups: branding, bot tokens, `remnawave_url` / `remnawave_token`,
`dashboard_login` / `dashboard_password` / `dashboard_secret`, `android_jwt_secret`,
`log_level`, `web_allowed_origins`, payment-gateway keys, `telemt_*`.

**Boot-time security checks:**
- **dashboard** refuses weak `dashboard_secret` or password `admin`.
- **miniapp** refuses missing/placeholder `android_jwt_secret`; requires
  `google_play_rtdn_token` when Google Play IAP is enabled.

### `.env`
Compose-level variables (`cp .env.example .env`):

```dotenv
POSTGRES_USER=xray
POSTGRES_PASSWORD=...        # required — compose refuses to start if empty
POSTGRES_DB=xray_vpn_bot
IMAGE_TAG=staging
# REGISTRY=ghcr.io/l0nelynx/  # default (pull from ghcr). Set EMPTY to build/run
#                             # fully locally without pulling (see below).
```

`DATABASE_URL` is composed automatically inside compose:
`postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}`.

## Networks

- **`backend-network`** (external) — edge network shared with reverse-proxy nginx.
  All app containers and `frontend` attach here.
- **`data-network`** (compose-managed) — Postgres and DB-connected backends.
  Postgres is **not** on `backend-network`, so the edge cannot reach the DB
  directly. The network is **not** `internal: true` in the default compose file:
  Postgres is also bound to `127.0.0.1:5432` on the host for backups and local
  tools. For stricter isolation (no host gateway on `data-network`), uncomment
  `internal: true` under `data-network` in `docker-compose.yml` and remove or
  restrict the Postgres host port mapping.
- **`mail-net`** (external) — used by `miniapp` for outbound SMTP.

## Images & build

Backends share a `python-base` image (common deps built once). The `frontend`
image builds both in-repo SPAs (dashboard + miniapp; npm workspaces) and serves
them with nginx. The browser **web portal** is a
[separate repo](https://github.com/l0nelynx/web-portal) deployed independently.

**Pull prebuilt images (default — from ghcr):**
```bash
docker compose pull
docker compose up -d
```

**Build locally from source.** Build the base image first, then the rest:
```bash
docker compose --profile build build base   # shared python-base
docker compose build                        # bot / dashboard / miniapp / frontend
docker compose up -d
```

**Build locally without touching ghcr** (test environments): set `REGISTRY=` in
`.env` (empty). Image names become local (`bot:staging`, `python-base:staging`,
…) and nothing is pulled. Then run the two build commands above.

Startup order: `postgres` (healthy) → `migrate` (completed) → `bot` / `dashboard`
/ `miniapp`. `frontend` has no backend dependency.

### Removed legacy mounts

Older compose files mounted Marzban TLS certs (`/var/lib/marzban/certs/`) and
`dig_data.json` into the bot container. **Neither is used by the current code**
(SSL terminates at the edge nginx; `dig_data.json` has no references). They are
not mounted in the current `docker-compose.yml`.

## Migrations

Schema is managed exclusively by Alembic (HEAD: `0014_support_attachments`). The
one-shot `migrate` container runs `alembic upgrade head` before the apps boot.
See [database.md](database.md).

## Logging

Miniapp log verbosity is controlled by `log_level` in `config.yml` (default:
`normal` = INFO). Accepted: `normal`, `debug`, `warning`, `error`, `critical`.
Do not set `LOG_LEVEL` in compose — use config instead.

## Reverse proxy

Run the stack behind an edge nginx that terminates TLS and routes traffic to the
backends and the `frontend` container. The exact, copy-pasteable config (using
the Docker-DNS resolver pattern so nginx doesn't fail when a backend is briefly
unresolvable) lives in the project
[README on GitHub](https://github.com/l0nelynx/xray-vpn-bot/blob/main/README.md#web-tier--reverse-proxy).
The edge nginx must share `backend-network`.

If the web portal is hosted separately (Vercel), route only
`/bot/miniapp/api/` to `miniapp:8001` and configure `web_allowed_origins` —
see [web-portal.md](web-portal.md).

## Host ports

For local debugging compose binds (loopback only):
`bot :5000`, `dashboard :8080→8000`, `miniapp :8001`, `frontend :8088→80`,
`postgres :5432`. In production traffic goes through the edge nginx, not these
host ports (except Postgres if you rely on local backups).

## Support-ticket image attachments

`miniapp` and `dashboard` share a read-write bind mount, `./support_uploads`,
for images attached to support-ticket replies (up to 3 images/message, 5MB
each). Before first use:

```bash
mkdir -p support_uploads
chown 10001:10001 support_uploads   # both containers run as non-root uid 10001
```

The edge nginx's `client_max_body_size` must also be raised above the 1MB
default — see the
[README on GitHub](https://github.com/l0nelynx/xray-vpn-bot/blob/main/README.md#web-tier--reverse-proxy)
(`client_max_body_size 20m;`). Without it, a 3-image reply silently 413s
before reaching either container.

## Scaling & workers (single-worker constraint)

Each backend runs as **one uvicorn worker in one container**. Several security
mechanisms keep state **in-process**, so this is load-bearing — do not add
`--workers N` or run multiple replicas without first externalising that state:

- **Rate limiting** (slowapi) and the **invite brute-force guard**
  (`services/miniapp/backend/web/brute_force.py`) — per-process counters.
- **Dashboard login throttle** (`services/dashboard/backend/login_guard.py`) —
  per-process.
- **Telegram OIDC PKCE store** and the **JWKS cache**
  (`services/miniapp/backend/web/web_router.py`) — a multi-worker setup would
  route the callback to a worker that never saw the `state`/`code_verifier`, so
  **Sign-in-with-Telegram would fail intermittently**.

To scale horizontally, move this state to Postgres/Redis (e.g. slowapi with a
Redis storage backend, a shared PKCE/throttle table) first.

**Rate-limit correctness depends on the edge nginx** setting `X-Real-IP`
(`proxy_set_header X-Real-IP $remote_addr;` — already in the README edge config).
The backends key every limit on that header; without it all clients collapse into
one bucket (the nginx container IP) and the limits/guards stop being per-client.

## CI

`.github/workflows/build.yml` (and `.gitlab-ci.yml`) build and push per-service
images to ghcr on pushes to `main` (`:latest`) and `develop` (`:staging`), plus
immutable `:sha-…` / `:build-…` tags. Only changed services rebuild; `python-base`
rebuilds only when its own inputs change and is otherwise reused.

## Documentation site

MkDocs Material builds `docs/` into a static site. Workflow: `.github/workflows/docs.yml`
(deploys via GitHub Actions → **Settings → Pages → Source: GitHub Actions**).

- **URL:** https://l0nelynx.github.io/xray-vpn-bot/
- **Config:** `mkdocs.yml` (nav, theme)
- **Local:** `pip install -r requirements-docs.txt && mkdocs serve`

**First-time setup:** repo **Settings → Pages → Build and deployment → Source → GitHub Actions**.
Then re-run the *Deploy documentation* workflow (or push to `main`). A 404 usually means
Pages is still set to «Deploy from branch» with the wrong branch, or Actions source was
never enabled.
