# Configuration

All runtime services read a single **`config.yml`** at the repo root (gitignored).
Copy `config-example.yml` and fill in your values. The file is mounted read-only
into `bot`, `dashboard`, and `miniapp`.

Compose-level variables live in **`.env`** (`cp .env.example .env`).

## Dual-source configuration (YAML + Dashboard)

Operator-facing settings are migrating from YAML into Postgres so they can be
edited in **Dashboard → Settings** without editing files or restarting.

**Precedence (dual-source period):**

1. **Dashboard / DB** — if a runtime key was saved, or a payment/app
   integration provider is `managed` (saved in UI).
2. Else **`config.yml`** — current behaviour; existing installs keep working.
3. Else **code defaults** (e.g. maintenance / Android TTL / SMTP port seed).

| Prefer Dashboard | Stay in YAML (bootstrap) |
|------------------|--------------------------|
| Maintenance mode | `token`, `admin_bot_token`, `admin_id` |
| `branding_name`, news/support/legal links | Remnawave URL/token/webhook secret |
| `free_days` / `free_traffic` | `dashboard_login` / `password` / `secret` |
| Remnawave squad IDs + `subscription_url` | `miniapp_url`, `bot_url`, `miniapp_tg_url` |
| Payment gateway credentials + enable | uvicorn / `log_level` / `expose_api_docs` |
| Android JWT + TTLs, SMTP, Telemt connection | SA **file paths** (JSON content preferred in Dashboard) |
| Store / FCM / Google Play / Web portal | `support_token`, path mounts |

On boot, missing runtime keys and integration providers are **imported from YAML**
(without overwriting Dashboard values). Saving in the UI makes Dashboard the
source of truth for that key/provider.

Optional bootstrap key: `payments_secrets_key` — encrypts credentials in
`payment_integrations` and `app_integrations`. If unset, `dashboard_secret` is used as a fallback.

Do **not** delete dual-source keys from production `config.yml` yet — they are
cut in later releases after the DB path is stable.

## `.env` (Docker Compose)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_USER` | No | `xray` | PostgreSQL username |
| `POSTGRES_PASSWORD` | **Yes** | — | Compose refuses to start if empty |
| `POSTGRES_DB` | No | `xray_vpn_bot` | Database name |
| `IMAGE_TAG` | No | `staging` | Image tag — see [Deployment](deployment.md#image-versioning). Examples: `staging`, `1.0.0-dev.42`, `1.0.0` |
| `REGISTRY` | No | `ghcr.io/l0nelynx/` | Image registry prefix. For Docker Hub use `docker.io/<your-dockerhub-username>/` — **must match** the `DOCKERHUB_USERNAME` GitHub secret (not necessarily the GitHub org name). Empty = local builds only. |

`DATABASE_URL` is composed automatically:

```
postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
```

## `config.yml` — core identity

| Key | Required | Description |
|-----|----------|-------------|
| `branding_name` | Yes | Service name shown to users |
| `token` | Yes | Main Telegram bot token |
| `bot_url` | Yes | `https://t.me/YourBot` — used in notifications |
| `miniapp_url` | Yes | HTTPS URL of the MiniApp page (WebApp button) |
| `miniapp_tg_url` | Yes | `https://t.me/YourBot/appname` — Telegram-side MiniApp link |

## Channels & public links

| Key | Required | Description |
|-----|----------|-------------|
| `news_id` | Yes | News channel numeric ID (bot must be admin) |
| `news_url` | Yes | Public invite link to the news channel |
| `support_bot_id` | Yes | Support contact (`@username` or `t.me/…`) |
| `agreement_url` | Yes | User agreement page URL |
| `policy_url` | Yes | Privacy policy page URL |

## Admin & notifications

| Key | Required | Description |
|-----|----------|-------------|
| `admin_id` | Yes | Admin Telegram user ID |
| `admin_bot_token` | No | Separate admin bot for broadcasts/alerts |
| `logs_id` | No | Chat/channel for event logs (registrations, invoices) |
| `web_id` | No | Chat for web-portal partnership inquiries |
| `admin_logs_length` | No | Rows in in-bot admin log panel (default `20`) |

## Webhook server (bot)

| Key | Default | Description |
|-----|---------|-------------|
| `uvicorn_host` | `0.0.0.0` | FastAPI bind host |
| `uvicorn_port` | `5000` | FastAPI bind port |

SSL terminates at the edge nginx — do not enable uvicorn SSL in production.

## Remnawave VPN panel

| Key | Required | Description |
|-----|----------|-------------|
| `remnawave_url` | Yes | Panel base URL (`https://…`) — **bootstrap YAML** |
| `remnawave_token` | Yes | API token from panel settings — **bootstrap YAML** |
| `remnawave_webhook_secret` | No | HMAC secret for inbound panel webhooks — **bootstrap YAML** |
| `rw_free_id` | Yes | Internal squad UUID for FREE users — preferred: Dashboard → Remnawave |
| `rw_pro_id` | Yes | Internal squad UUID for PRO users — preferred: Dashboard → Remnawave |
| `rw_ext_free_id` | No | External squad for FREE users — preferred: Dashboard → Remnawave |
| `rw_ext_pro_id` | No | External squad for PRO users — preferred: Dashboard → Remnawave |
| `subscription_url` | No | Subscription base URL (Android deep-link validation) — preferred: Dashboard → Remnawave |

## Dashboard

| Key | Required | Description |
|-----|----------|-------------|
| `dashboard_login` | Yes | Admin login |
| `dashboard_password` | Yes | Admin password — **must not** be `admin` (boot refuses) |
| `dashboard_secret` | Yes | JWT signing secret — ≥32 bytes, not the built-in default |
| `expose_api_docs` | No | `false` in production — enables Swagger on dashboard + miniapp APIs |

Generate secrets:

```bash
openssl rand -hex 32
```

## Telemt (optional)

Preferred: **Dashboard → Telemt → Connection** (URL in runtime settings; header encrypted).

| Key | Description |
|-----|-------------|
| `telemt_server` | Telemt API base URL — omit to disable Telemt features |
| `telemt_header` | Authorization header forwarded to Telemt |

## Free plan defaults

| Key | Default | Description |
|-----|---------|-------------|
| `free_days` | `30` | Free plan duration |
| `free_traffic` | `10` | Free plan traffic limit (GB) |

## Android / mobile

Preferred: **Dashboard → Settings → Android** (JWT secret encrypted).

| Key | Required | Description |
|-----|----------|-------------|
| `android_jwt_secret` | For Android | HS256 JWT signing key — ≥32 bytes |
| `android_access_ttl` | No | Access token TTL seconds (default `900`) |
| `android_refresh_ttl` | No | Refresh token TTL (default `5184000` = 60 days) |
| `android_jwt_issuer` | No | JWT `iss` claim (default `xray-vpn-bot`) |

## Email (SMTP)

Preferred: **Dashboard → Settings → Email**. Miniapp joins `mail-net` for outbound SMTP.

| Key | Required | Description |
|-----|----------|-------------|
| `smtp_host` | For email | SMTP server |
| `smtp_port` | No | Default `587` (STARTTLS); use `465` for implicit TLS |
| `smtp_user` | For email | SMTP login |
| `smtp_password` | For email | SMTP password (encrypted in Dashboard) |
| `smtp_from` | No | Sender display name + address |
| `smtp_use_tls` | No | `true` = implicit TLS on 465 |
| `email_code_ttl` | No | Verification code TTL (default `900`) |
| `email_code_max_attempts` | No | Max failed attempts (default `5`) |

## Google Play IAP (optional)

Preferred: **Dashboard → Settings → Push / Play** (paste SA JSON; path is fallback).

| Key | Description |
|-----|-------------|
| `google_play_package_name` | Play Console package name |
| `google_play_service_account_path` | Bootstrap fallback path to SA JSON inside container |
| `google_play_rtdn_token` | RTDN webhook shared secret — required when package name is set |

## FCM push (optional)

Token registration works without these keys; sending from Dashboard requires project id + SA (JSON or path).

| Key | Description |
|-----|-------------|
| `fcm_project_id` | Firebase / GCP project id — preferred: Dashboard Push/Play |
| `fcm_service_account_path` | Bootstrap fallback path (`/app/fcm-sa.json`) |

## Web portal (CORS)

Preferred: **Dashboard → Settings → Web**.

| Key | Description |
|-----|-------------|
| `web_allowed_origins` | List of portal SPA origins — required when portal is on a separate domain |
| `tg_client_secret` | Telegram OIDC Client Secret from BotFather (encrypted in Dashboard) |

See [web-portal.md](web-portal.md).

## Support bot (legacy)

| Key | Description |
|-----|-------------|
| `support_token` | Token for standalone `support.py` bot (own SQLite DB) |

## Payment gateways

Only fill in gateways you use. Full setup guide: [Payment gateways](payment-gateways.md).

### CryptoBot

| Key | Description |
|-----|-------------|
| `crypto_bot_token` | @CryptoBot API token |

### Crystal Pay

| Key | Description |
|-----|-------------|
| `crystal_login` | Merchant login |
| `crystal_secret` | API secret |
| `crystal_salt` | Webhook salt |
| `crystal_webhook` | Public callback URL (`https://your-domain/bot/crystal_webhook`) |

### A-Pays (SBP)

| Key | Description |
|-----|-------------|
| `apay_id` | Merchant ID |
| `apay_secret` | Secret key |
| `apay_api_url` | API base URL (default `https://apays.io`) |

### Platega

| Key | Description |
|-----|-------------|
| `platega_merchant_id` | Merchant UUID (`X-MerchantId`) |
| `platega_api_key` | API key (`X-Secret`) |
| `platega_url` | API base URL |
| `platega_payment_method` | Default method: `2`=SBP, `3`=ERIP, `11`=card, `12`=intl, `13`=crypto |

### ParityPay

| Key | Description |
|-----|-------------|
| `paritypay_shop_id` | Shop UUID |
| `paritypay_secret_1` | Signs outgoing API requests |
| `paritypay_secret_2` | Verifies incoming webhooks |
| `paritypay_url` | API base URL |
| `paritypay_webhook` | Public callback URL (optional — can set in cassa UI) |
| `paritypay_service` | Default service: `sbp` or `card` |

### Telegram Bot purchase runtime

Prices, currencies, methods, duration and delivery squads come only from
Dashboard → Tariff Constructor. The `legacy_bot_constructor` flag switches the
Bot between that tree and the MiniApp fallback within five seconds; no restart
is required. Legacy YAML prices, tariff plans and squad profiles are removed.

## Currency rates (Dashboard stats)

USD→RUB is fetched from the CBR API (cached). Stars use a fixed `1.3` RUB
multiplier. Config overrides (`star_rub_rate` / `usd_rub_rate`) were removed.

## Store (optional)

Preferred: **Dashboard → Settings → Store**.

| Key | Description |
|-----|-------------|
| `store_url` | External store API base URL |
| `store_api_token` | Store API token (encrypted in Dashboard) |

Omit both to hide the Store section in Dashboard.

## Logging

| Key | Default | Description |
|-----|---------|-------------|
| `log_level` | `normal` | Miniapp verbosity: `normal`, `debug`, `warning`, `error`, `critical` |

Do not set `LOG_LEVEL` in compose — use `config.yml`.

## Advanced paths

| Key | Default | Description |
|-----|---------|-------------|
| `connect_app_config_path` | `/app/app-config.json` | Connect page catalog override — see [connect-page.md](connect-page.md) |
| `support_uploads_dir` | `/app/support_uploads` | Support ticket image storage |

## Boot-time security checks

The services **refuse to start** with insecure defaults:

| Service | Check |
|---------|-------|
| Dashboard | `dashboard_secret` must be ≥32 bytes and not the built-in placeholder |
| Dashboard | `dashboard_password` must not be `admin` |
| Miniapp | `android_jwt_secret` must not be missing/placeholder/short |
| Miniapp | `google_play_rtdn_token` required when `google_play_package_name` is set |

## Config file locations in containers

| Service | Mount path |
|---------|------------|
| `bot` | `/usr/src/app/config.yml` |
| `dashboard` | `/app/config.yml` |
| `miniapp` | `/app/config.yml` |
| `support-bot` | `/usr/src/app/config.yml` |
