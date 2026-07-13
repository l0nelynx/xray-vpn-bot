# Deployment

Production deployment via Docker Compose. For prerequisites and the high-level
flow, see [Getting started](getting-started.md). For every config key, see
[Configuration](configuration.md).

## Prerequisites

- Linux server with Docker + Docker Compose v2
- Domain with TLS (edge nginx, Caddy, or Traefik)
- Telegram bot token(s)
- Remnawave panel URL + API token + squad UUIDs
- Strong passwords for PostgreSQL and Dashboard

## Step-by-step first deploy

### 1. Clone and configure

```bash
git clone https://github.com/l0nelynx/xray-vpn-bot.git
cd xray-vpn-bot
cp config-example.yml config.yml
cp .env.example .env
```

Edit `config.yml` — minimum required keys listed in [Configuration](configuration.md).

Edit `.env` — set `POSTGRES_PASSWORD` (compose refuses empty value).

Generate secrets:

```bash
openssl rand -hex 32   # dashboard_secret, android_jwt_secret
```

### 2. Create Docker networks

```bash
docker network create backend-network
docker network create mail-net
```

| Network | Purpose |
|---------|---------|
| `backend-network` | Shared with edge nginx; all app containers attach here |
| `mail-net` | SMTP egress for miniapp email verification |
| `data-network` | Compose-managed; Postgres + DB-connected backends only |

### 3. Prepare support uploads (before first ticket reply)

```bash
mkdir -p support_uploads
chown 10001:10001 support_uploads
```

Both `miniapp` and `dashboard` containers run as uid `10001` and share this
directory for support-ticket image attachments.

### 4. Pull or build images

=== "Pull prebuilt (recommended)"

    ```bash
    docker compose pull
    docker compose up -d
    ```

    Images from `ghcr.io/l0nelynx/` — tag controlled by `IMAGE_TAG` in `.env`
    (`latest` from `main`, `staging` from `develop`).

=== "Build locally"

    ```bash
    docker compose --profile build build base   # shared python-base
    docker compose build                        # bot / dashboard / miniapp / frontend
    docker compose up -d
    ```

=== "Build without ghcr"

    Set `REGISTRY=` (empty) in `.env`, then run the build commands above.
    Image names become local (`bot:staging`, etc.).

### 5. Verify startup

```bash
docker compose ps
docker compose logs migrate    # should show Alembic upgrade success
docker compose logs bot --tail 20
```

Startup order:

```
postgres (healthy) → migrate (completed) → bot / dashboard / miniapp → frontend
```

Check health endpoints:

```bash
curl -s http://127.0.0.1:5000/health          # bot
curl -s http://127.0.0.1:8080/health          # dashboard
curl -s http://127.0.0.1:8001/health          # miniapp
```

### 6. Configure edge nginx

See [Reverse proxy](#reverse-proxy) below.

### 7. Register webhooks

Point each payment gateway callback to your public domain:

```
https://your-domain/bot/cryptopay_webhook
https://your-domain/bot/crystal_webhook
https://your-domain/bot/apays_webhook
https://your-domain/bot/platega_webhook
https://your-domain/bot/paritypay_webhook
```

See [Payment gateways](payment-gateways.md).

### 8. Configure product in Dashboard

1. Open `https://your-domain/bot/dashboard/`
2. Create squad profiles → build Tariff Constructor tree → set promos
3. Test purchase via MiniApp

## Containers

| Container | Image | Internal port | Host port (debug) |
|-----------|-------|---------------|-------------------|
| `postgres` | `postgres:16-alpine` | `5432` | `127.0.0.1:5432` |
| `migrate` | `bot` image | — | one-shot |
| `bot` | `ghcr.io/l0nelynx/bot` | `5000` | `127.0.0.1:5000` |
| `support-bot` | `support-bot` | — | no port |
| `dashboard` | `dashboard` | `8000` | `127.0.0.1:8080` |
| `miniapp` | `miniapp` | `8001` | `127.0.0.1:8001` |
| `frontend` | `frontend` | `80` | `127.0.0.1:8088` |

The `bot` container keeps network alias `seller-bot` for backwards-compatible
nginx configs.

`python-base` is build-time only (profile `build`) — not a runtime service.

## Networks detail

### backend-network (external)

Edge nginx, `bot`, `dashboard`, `miniapp`, `frontend`, `support-bot`.

Postgres is **not** on this network — the edge cannot reach the database directly.

### data-network (compose-managed)

`postgres`, `bot`, `dashboard`, `miniapp`, `migrate`.

Postgres binds `127.0.0.1:5432` on the host for backups and local tools. The
network is not `internal: true` by default. For stricter isolation, uncomment
`internal: true` under `data-network` in `docker-compose.yml` and remove the
host port mapping.

### mail-net (external)

`miniapp` only — outbound SMTP for email verification codes.

## Images & CI

Backends share a `python-base` image (FastAPI, SQLAlchemy, `common_db`,
`remnawave_client` built once). The `frontend` image bakes both SPAs.

CI (`.github/workflows/build.yml`, `.gitlab-ci.yml`):

| Branch | Tag |
|--------|-----|
| `main` | `:latest` |
| `develop` | `:staging` |
| any | `:sha-<short>`, `:build-<n>` |

`python-base` rebuilds only when its own inputs change; service-only changes
reuse the published base.

## Migrations

Schema: Alembic HEAD `0014_support_attachments`. The `migrate` container runs
`alembic upgrade head` before apps boot. Dashboard and miniapp also call
`upgrade_to_head()` on startup (no-op if current).

Details: [database.md](database.md).

## Reverse proxy

The edge nginx terminates TLS and routes by URL prefix. Every API path is under
`.../api`, so the static-vs-API split is unambiguous.

| Path | Target |
|------|--------|
| `/bot/dashboard/api/…` | `dashboard:8000` |
| `/bot/dashboard/…` | `frontend:80` |
| `/bot/miniapp/api/…` | `miniapp:8001` |
| `/bot/miniapp/…` | `frontend:80` |
| `/bot/…` | `bot:5000` |
| `/` | `frontend:80` or external web portal |

!!! danger "Do not use static upstream blocks"
    `upstream { server dashboard:8000; }` resolves hostnames **at nginx startup**
    and fails with `[emerg] host not found in upstream` if a backend isn't ready.
    Use Docker's embedded DNS (`127.0.0.11`) with a **variable** to defer
  resolution to request time.

```nginx
server {
    listen 443 ssl;
    server_name example.com;
    # ssl_certificate / ssl_certificate_key ...

    # Support-ticket images (up to 3 × 5 MB) exceed nginx 1 MB default.
    client_max_body_size 20m;

    # Docker embedded DNS — required for runtime resolution.
    resolver 127.0.0.11 valid=30s ipv6=off;

    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # APIs — longest-prefix match wins.
    location /bot/dashboard/api/ {
        set $up dashboard:8000;
        proxy_pass http://$up$request_uri;
    }
    location /bot/miniapp/api/ {
        set $up miniapp:8001;
        proxy_pass http://$up$request_uri;
    }

    # SPAs (static).
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

    # Public entry.
    location / {
        set $up frontend:80;
        proxy_pass http://$up$request_uri;
    }
}
```

The edge nginx must join `backend-network` so container names resolve.

### Web portal on separate host

If the browser portal is on Vercel, route only `/bot/miniapp/api/` to miniapp
and set `web_allowed_origins` in config. See [web-portal.md](web-portal.md).

## Support-ticket attachments

Shared read-write mount `./support_uploads` between `miniapp` and `dashboard`.

- Up to 3 images per message, 5 MB each
- Containers run as uid `10001` — host directory must be writable
- Edge `client_max_body_size 20m` required (see nginx config above)

## Logging

Miniapp verbosity: `log_level` in `config.yml` (default `normal` = INFO).
Values: `normal`, `debug`, `warning`, `error`, `critical`.

Do not set `LOG_LEVEL` in compose.

## Scaling constraints

Each backend runs **one uvicorn worker in one container**. Do not add `--workers N`
or multiple replicas without externalising in-process state:

| Mechanism | Location |
|-----------|----------|
| Rate limiting (slowapi) | All backends |
| Invite brute-force guard | `miniapp/web/brute_force.py` |
| Dashboard login throttle | `dashboard/login_guard.py` |
| Telegram OIDC PKCE store | `miniapp/web/web_router.py` |
| JWKS cache | `miniapp/web/web_router.py` |

Multi-worker miniapp would break Sign-in-with-Telegram (PKCE `state` routed to
wrong worker). To scale horizontally, move state to Postgres or Redis first.

**Rate-limit correctness** requires `X-Real-IP` from edge nginx (included in the
config above). Without it, all clients share one bucket.

## Updates

```bash
docker compose pull
docker compose up -d
```

Migrations run automatically via the `migrate` container on each `up`.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `config file not found` | Mount `config.yml` — check `volumes:` in compose |
| `dashboard_secret` boot error | `openssl rand -hex 32`, replace placeholder |
| `POSTGRES_PASSWORD must be set` | Fill `.env` |
| Payment webhooks 404 | Edge must route `/bot/` → `bot:5000` with HTTPS |
| Dashboard 401 | Check `dashboard_login` / `dashboard_password` |
| Remnawave connection failed | Verify URL includes `https://`, token valid, squad UUIDs exist |
| Telemt 503 in Dashboard | `telemt_server` empty or unreachable |
| Support image upload 413 | Raise `client_max_body_size` on edge nginx |
| nginx upstream not found | Use variable + resolver pattern (see above) |
| MiniApp 403 username required | User must have a Telegram @username |

## Documentation site

MkDocs Material builds `docs/` into a static site.

| Item | Value |
|------|-------|
| URL | https://l0nelynx.github.io/xray-vpn-bot/ |
| Workflow | `.github/workflows/docs.yml` |
| Local preview | `pip install -r requirements-docs.txt && mkdocs serve` |

First-time: repo **Settings → Pages → Source → GitHub Actions**.

## Removed legacy mounts

Older compose files mounted Marzban TLS certs and `dig_data.json` into the bot.
Neither is used — SSL terminates at edge nginx. Not mounted in current compose.
