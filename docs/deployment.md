# Deployment

Containerised deployment via Docker Compose. See [architecture.md](architecture.md)
for the container list and networking model.

## Prerequisites

- Docker + Docker Compose.
- A Telegram bot token (and optionally separate admin/support tokens).
- A Remnawave URL + API token.
- (Optional) payment-gateway credentials.

## Configuration

### `config.yml`
Application config (tokens, Remnawave, dashboard creds, payment keys, branding):

```bash
cp config-example.yml config.yml   # then edit
```

It is mounted read-only into the backends (`bot`, `dashboard`, `miniapp`) and the
`support-bot`. Key groups: branding, bot tokens, `remnawave_url` /
`remnawave_token`, `dashboard_login` / `dashboard_password` / `dashboard_secret`,
payment-gateway keys, `telemt_*`.

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

```bash
docker network create backend-network    # external edge network (once)
```
`backend-network` (edge) is external and shared with the reverse-proxy nginx.
`data-network` (private, `internal: true`) is created by compose and carries
PostgreSQL — it has no gateway, so the DB is never exposed outward.

## Images & build

Backends share a `python-base` image (common deps built once). The `frontend`
image builds both SPAs (npm workspaces) and serves them with nginx.

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

Startup order is enforced by `depends_on`: `postgres` (healthy) → `migrate`
(completed) → `bot` / `dashboard` / `miniapp`. `frontend` is independent.

## Migrations

Schema is managed exclusively by Alembic. The one-shot `migrate` container runs
`alembic upgrade head` before the apps boot; they wait on it via
`depends_on: service_completed_successfully`. See [database.md](database.md).

## Reverse proxy

Run the stack behind an edge nginx that terminates TLS and routes traffic to the
backends and the `frontend` container. The exact, copy-pasteable config (using
the Docker-DNS resolver pattern so nginx doesn't fail when a backend is briefly
unresolvable) lives in the project [README](../README.md) → "Web tier & reverse
proxy". The edge nginx must share `backend-network`.

## Host ports

For local debugging compose binds (loopback only):
`bot :5000`, `dashboard :8080→8000`, `frontend :8088→80`. In production traffic
goes through the edge nginx, not these host ports.

## Scaling & workers (single-worker constraint)

Each backend runs as **one uvicorn worker in one container**. Several security
mechanisms keep state **in-process**, so this is load-bearing — do not add
`--workers N` or run multiple replicas without first externalising that state:

- **Rate limiting** (slowapi) and the **invite brute-force guard**
  (`miniapp/.../web/brute_force.py`) — per-process counters.
- **Dashboard login throttle** (`dashboard/.../login_guard.py`) — per-process.
- **Telegram OIDC PKCE store** and the **JWKS cache** (`miniapp/.../web/web_router.py`)
  — a multi-worker setup would route the callback to a worker that never saw the
  `state`/`code_verifier`, so **Sign-in-with-Telegram would fail intermittently**.

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
