# Database

Production runs on **PostgreSQL 16** (separate `postgres` container, data on the
`./pg_data` volume). A **SQLite fallback** is used for local dev when
`DATABASE_URL` is unset. The schema is defined as SQLAlchemy ORM and applied with
Alembic.

All backends (`bot`, `dashboard`, `miniapp`) share the same database through the
`common_db` package. The legacy `support-bot` keeps its own SQLite under `./db/`.

## Single source of truth: `common_db`

`packages/common_db` owns everything DB-related, shared by every backend:

- **`common_db.base`** — the single `Base` / `Base.metadata` (Alembic
  autogenerates against it).
- **`common_db.models`** — all ORM models (`users`, `transactions`, `tariffs`,
  `promos`, `support`, `menus`, `google_play`, `auth`, `system`, …).
- **`common_db.repo`** — reusable query helpers (users, promos, support, system)
  so query logic isn't duplicated across services.
- **`common_db.url` / `common_db.session`** — `DATABASE_URL` resolution and the
  async engine/sessionmaker factory.

The backend selected by `DATABASE_URL`:
- `postgresql+asyncpg://…@postgres:5432/…` — production (async driver).
- unset → `sqlite+aiosqlite:///…` — local dev fallback.
Sync variants (`postgresql+psycopg2://…`, `sqlite:///…`) are used by Alembic.

## Key tables

| Table | Purpose |
|-------|---------|
| `users` | Telegram/web/Android users + VPN profile (`tg_id`, `email`, `vless_uuid`, `is_banned`, `language`, `vip`). |
| `transactions` | Payments/orders (`transaction_id`, `order_status`, `payment_method`, `amount`, `days_ordered`, `tariff_slug`, `delivery_status`). |
| `tariff_plans` / `tariff_prices` | Subscription plans + per-currency pricing; `squad_id` binds a plan to a Remnawave squad. |
| `promos` / `promo_redemptions` | Promo codes, discounts, bonus days, referrals. |
| `support_tickets` / `support_messages` | In-app support ticketing. |
| `menu_screens` / `menu_buttons` (webapp menu) | Dynamic menu structure configured in the Dashboard. |
| `google_play_*` | Google Play IAP SKUs and purchases. |
| `email_verifications` / `refresh_tokens` | Web/Android registration + JWT refresh. |

The full, authoritative set lives in `packages/common_db/common_db/models/`.

## Migrations

Schema changes go exclusively through **Alembic** (`alembic/versions/`). Current
HEAD: **`0014_support_attachments`**. The one-shot `migrate` container runs
`alembic upgrade head` on startup; the app services wait for it (`depends_on: service_completed_successfully`) and run no
ad-hoc DDL of their own.

- Autogenerate target is `common_db.Base.metadata` (`alembic/env.py`).
- Local dev without Docker:
  `python -c "from migrations_runner import upgrade_to_head; upgrade_to_head()"`.
- Drift guards in `packages/common_db/tests/` keep models, the canonical table
  set and Alembic HEAD aligned.
