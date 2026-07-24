# Database

Production runs on **PostgreSQL 16** (separate `postgres` container, data on the
`./pg_data` volume). A **SQLite fallback** is used for local dev when
`DATABASE_URL` is unset. The schema is defined as SQLAlchemy ORM and applied with
Alembic.

All backends (`bot`, `dashboard`, `miniapp`, `crm-worker`) share the same database
through the `common_db` package. The legacy `support-bot` keeps its own SQLite
under `./db/`. Redis is used for CRM job queues only — not as primary storage.

## Single source of truth: `common_db`

`packages/common_db` owns everything DB-related, shared by every backend:

- **`common_db.base`** — the single `Base` / `Base.metadata` (Alembic
  autogenerates against it).
- **`common_db.models`** — all ORM models (`users`, `transactions`,
  `promos`, `crm`, `support`, `menus`, `google_play`, `auth`, `system`, …).
- **`common_db.repo`** — reusable query helpers (users, promos, referral_rewards,
  balance, crm, support, system) so query logic isn't duplicated across services.
- **`common_db.url` / `common_db.session`** — `DATABASE_URL` resolution and the
  async engine/sessionmaker factory.

The backend selected by `DATABASE_URL`:
- `postgresql+asyncpg://…@postgres:5432/…` — production (async driver).
- unset → `sqlite+aiosqlite:///…` — local dev fallback.
Sync variants (`postgresql+psycopg2://…`, `sqlite:///…`) are used by Alembic.

## Key tables

| Table | Purpose |
|-------|---------|
| `users` | Telegram/web/Android users + VPN profile (`tg_id`, `email`, `vless_uuid`, `is_banned`, `language`, `vip`, **`bonus_credits`**). |
| `transactions` | Payments/orders. `transaction_id` is the local UUID; `provider_invoice_id` is the webhook correlation key; squads, traffic policy and Remnawave metadata form the immutable delivery snapshot. |
| `promos` | Promo/referral **code catalog** (`promo_type`, `credit_grant`, `days_purchased`, `points_rewarded`). See [referral.md](referral.md). |
| `promo_redemptions` | Audit log of code activations (gating rules). |
| `promo_settings` | Singleton tunables: `default_credit_grant`, `points_reward_per_30`, `reward_cap_points`. |
| `credit_ledger` | Append-only wallet ledger (`SOURCE_PROMO`, `SOURCE_CRM`, `SOURCE_PAYMENT`, …). |
| `crm_campaigns` / `crm_campaign_deliveries` | CRM ad-hoc campaigns and per-recipient results. See [crm.md](crm.md). |
| `crm_events` / `crm_event_deliveries` | Scheduled CRM events + repeat-policy tracking. |
| `support_tickets` / `support_messages` | In-app support ticketing. |
| `menu_screens` / `menu_buttons` | Telegram Bot system and custom screens. |
| `webapp_menu_nodes` | The single RU/EN tariff tree for Telegram Bot, MiniApp, web and Android. |
| `google_play_*` | Google Play IAP SKUs and purchases. |
| `email_verifications` / `refresh_tokens` | Web/Android registration + JWT refresh. |

The full, authoritative set lives in `packages/common_db/common_db/models/`.

## Migrations

Schema changes go exclusively through **Alembic** (`alembic/versions/`). Current
HEAD: **`0030_tariff_delivery_options`**. The one-shot `migrate` container runs
`alembic upgrade head` on startup; the app services wait for it (`depends_on:
service_completed_successfully`) and run no ad-hoc DDL of their own.

Notable recent migrations:

| Revision | What it introduced |
|----------|-------------------|
| `0012` | `promo_redemptions`, `promo_type`, referral settings |
| `0015`–`0018` | CRM campaigns, events, conditions/actions JSON |
| `0019` | `users.bonus_credits`, `credit_ledger`, `promos.credit_grant` |
| `0020` | Points scale (×10 RUB points) |
| `0021` | Owner rewards in points (`points_rewarded`, `points_reward_per_30`, `reward_cap_points`) |
| `0029` | Unified tariff tree, delivery snapshots, provider IDs; removes legacy tariff/squad tables |
| `0030` | Multi-squad tariff delivery, traffic policy and Remnawave description/tag snapshots |

- Autogenerate target is `common_db.Base.metadata` (`alembic/env.py`).
- Local dev without Docker:
  `python -c "from migrations_runner import upgrade_to_head; upgrade_to_head()"`.
- Drift guards in `packages/common_db/tests/` keep models, the canonical table
  set and Alembic HEAD aligned.
