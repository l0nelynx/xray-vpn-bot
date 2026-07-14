# Configuration

All runtime services read a single **`config.yml`** at the repo root (gitignored).
Copy `config-example.yml` and fill in your values. The file is mounted read-only
into `bot`, `dashboard`, and `miniapp`.

Compose-level variables live in **`.env`** (`cp .env.example .env`).

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
| `remnawave_url` | Yes | Panel base URL (`https://…`) |
| `remnawave_token` | Yes | API token from panel settings |
| `remnawave_webhook_secret` | No | HMAC secret for inbound panel webhooks — see [Integrations](integrations.md) |
| `rw_free_id` | Yes | Internal squad UUID for FREE users |
| `rw_pro_id` | Yes | Internal squad UUID for PRO users |
| `rw_ext_free_id` | No | External squad for FREE users |
| `rw_ext_pro_id` | No | External squad for PRO users |
| `subscription_url` | No | Base URL for subscription links (Android deep-link validation) |

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

| Key | Description |
|-----|-------------|
| `telemt_server` | Telemt API base URL — omit to disable Dashboard Telemt pages |
| `telemt_header` | Authorization header forwarded to Telemt |

## Free plan defaults

| Key | Default | Description |
|-----|---------|-------------|
| `free_days` | `30` | Free plan duration |
| `free_traffic` | `10` | Free plan traffic limit (GB) |

## Android / mobile

| Key | Required | Description |
|-----|----------|-------------|
| `android_jwt_secret` | For Android | HS256 JWT signing key — ≥32 bytes |
| `android_access_ttl` | No | Access token TTL seconds (default `900`) |
| `android_refresh_ttl` | No | Refresh token TTL (default `5184000` = 60 days) |
| `android_jwt_issuer` | No | JWT `iss` claim (default `xray-vpn-bot`) |

## Email (SMTP)

Required for Android/web email verification. Miniapp joins `mail-net` for outbound SMTP.

| Key | Required | Description |
|-----|----------|-------------|
| `smtp_host` | For email | SMTP server |
| `smtp_port` | No | Default `587` (STARTTLS); use `465` for implicit TLS |
| `smtp_user` | For email | SMTP login |
| `smtp_password` | For email | SMTP password |
| `smtp_from` | No | Sender display name + address |
| `smtp_use_tls` | No | `true` = implicit TLS on 465 |
| `email_code_ttl` | No | Verification code TTL (default `900`) |
| `email_code_max_attempts` | No | Max failed attempts (default `5`) |

## Google Play IAP (optional)

| Key | Description |
|-----|-------------|
| `google_play_package_name` | Play Console package name |
| `google_play_service_account_path` | Path to service-account JSON inside container |
| `google_play_rtdn_token` | RTDN webhook shared secret — required when package name is set |

## Web portal (CORS)

| Key | Description |
|-----|-------------|
| `web_allowed_origins` | List of portal SPA origins — required when portal is on a separate domain |
| `tg_client_secret` | Telegram OIDC Client Secret from BotFather — enables "Sign in with Telegram" |

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

### Legacy bot constructor prices

Used only when `legacy_bot_constructor = true` in Dashboard → WebApp → Settings.
After enabling, **restart the bot**.

| Key | Description |
|-----|-------------|
| `stars_price` | 1-month base price in Telegram Stars |
| `crypto_price` | 1-month base price in USDT |
| `sbp_price` | 1-month base price in RUB |
| `discount` | Extra discount (%) for 3+ month plans |

## Currency rates (Dashboard stats)

| Key | Description |
|-----|-------------|
| `star_rub_rate` | Telegram Stars → RUB override (default `1.3`) |
| `usd_rub_rate` | USD → RUB fallback when CBR API is unreachable |

## Store (optional)

| Key | Description |
|-----|-------------|
| `store_url` | External store API base URL |
| `store_api_token` | Store API token |

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
