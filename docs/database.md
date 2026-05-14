# Database Schema

The project runs against **PostgreSQL 16** in production (separate `postgres` container, data on the `./pg_data` volume), with a **SQLite fallback** for local development when `DATABASE_URL` is not set. Schema is defined via SQLAlchemy ORM and applied through Alembic.

All services (`seller-bot`, `miniapp`, `dashboard`) share the same database. `support-bot` keeps its own SQLite file under `./db/` and is unaffected by the Postgres switch.

The active backend is selected by the `DATABASE_URL` environment variable:
- `postgresql+asyncpg://user:pw@postgres:5432/xray_vpn_bot` — production, async driver for the apps.
- unset → `sqlite+aiosqlite:///db/db.sqlite3` — local dev fallback (resolved by `app/db_url.py`).

Sync variants (`postgresql+psycopg2://...`, `sqlite:///...`) are used by Alembic and the one-shot data migrator only.

## Main Tables

### `users`
Stores information about Telegram users and their VPN profiles.
- `id`: Internal primary key.
- `tg_id`: Telegram User ID (unique).
- `username`: Telegram username.
- `vless_uuid`: The UUID assigned to the user in the VPN panel.
- `api_provider`: The VPN panel provider (e.g., "remnawave").
- `email`: User email (often used as the identifier in Remnawave).
- `is_banned`: Boolean flag for user access.
- `language`: User's preferred language (en/ru).
- `vip`: Integer flag for VIP status.

### `transactions`
Records all payment attempts and completed orders.
- `transaction_id`: External ID from the payment provider.
- `vless_uuid`: User's VPN UUID.
- `order_status`: Current status (e.g., "paid", "pending").
- `payment_method`: Provider used (e.g., "cryptobot", "stars").
- `amount`: Transaction amount.
- `days_ordered`: Duration of the purchased subscription.
- `tariff_slug`: Identifier of the purchased tariff.

### `tariff_plans`
Defines the available VPN subscription plans.
- `name`: Display name.
- `slug`: Unique identifier.
- `duration_days`: Plan length.
- `is_active`: Visibility toggle.
- `squad_id`: The Remnawave squad assigned to this plan.

### `tariff_prices`
Stores pricing for tariffs in different currencies.
- `tariff_id`: Link to `tariff_plans`.
- `currency`: e.g., "stars", "usdt", "rub".
- `amount`: The price value.

### `promos`
Manages promotional codes and rewards.
- `promo_code`: The code string.
- `discount_percent`: Percentage discount.
- `days_rewarded`: Extra days granted.

### `support_tickets` & `support_messages`
Handles support interactions.
- `subject`: Ticket topic.
- `message`: Initial user message.
- `status`: "open", "closed", etc.
- `messages`: Individual replies between user and admin.

### `webapp_menu_nodes`
Stores the dynamic menu structure configured in the Dashboard.
- `parent_id`: For nested menus.
- `text`: Button label.
- `action`: Type of action (e.g., "link", "buttons", "invoice").

## Migration & Initialization

Schema is managed exclusively by **Alembic** (`alembic/versions/`). The `migrate` init container in `docker-compose.yml` runs `alembic upgrade head` once on startup; `seller-bot`, `miniapp`, and `dashboard` wait for it via `depends_on: service_completed_successfully` before they boot.

- Online services no longer run ad-hoc DDL — the legacy `_check_and_migrate` (bot) and dashboard startup DDL were folded into Alembic revision `0006_postgres_compat`.
- For local dev without Docker, run `python -c "from migrations_runner import upgrade_to_head; upgrade_to_head()"` after creating the SQLite file.
- One-shot SQLite → Postgres data copy lives in `scripts/sqlite_to_postgres.py` (see `docs/postgres-migration-runbook.md`).
