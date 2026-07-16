# Dashboard

The Dashboard is the operator admin panel for managing the entire VPN sales
stack. It is a **React 18 + Ant Design v6** SPA at `/bot/dashboard/`, backed
by a **FastAPI JSON API** at `/bot/dashboard/api/`.

**Source:**

- Frontend: `web/apps/dashboard/`
- Backend: `services/dashboard/backend/`

## Access & authentication

| Item | Value |
|------|-------|
| URL | `https://your-domain/bot/dashboard/` |
| Login | `dashboard_login` / `dashboard_password` from `config.yml` |
| Token | JWT (HS256, 24h), stored in browser `localStorage` |
| Secret | `dashboard_secret` — boot refuses weak defaults |

Login is rate-limited: 10 failures per 15 minutes per IP → 15-minute block.
Behind nginx, ensure `X-Real-IP` is set (see [Deployment](deployment.md)).

After login you land on the **Overview** page with period KPIs and charts.

## Navigation structure

The sidebar is grouped into four sections:

| Section | Pages | Visible when |
|---------|-------|--------------|
| **Overview** | Dashboard, Users, Transactions, Statistics, Promocodes, CRM, Support, TG Admin | Always |
| **Bot Constructor** | Tariffs, Menus, Squads | `legacy_bot_constructor = true` |
| **Services** | Telemt, Store | Always (503 if not configured) |
| **WebApp** | Tariff Constructor, Settings | Always |

Toggle **Bot Constructor** visibility in **WebApp → Settings** (requires bot
restart after change).

---

## Overview (home)

**Route:** `/`

Period selector: today, yesterday, week, month, 6 months.

**KPI cards:**

- Revenue (RUB-normalized across currencies)
- New users
- Orders
- Average order value

Each card shows delta vs the previous period. An all-time strip shows total
users, active subscriptions, conversion %, and lifetime revenue.

**Charts:**

- Revenue over time
- Payment method breakdown (pie)
- User growth

**Recent transactions** — last 10 orders with status and amount.

---

## Users

**Route:** `/users`

Server-side paginated table with search (username, email, `vless_uuid`, `tg_id`)
and filters: all / paid / free / banned.

**Inline actions:**

- Ban / unban
- VIP toggle
- Delete user (cascades transactions)

**User drawer** (click a row):

- Edit identifiers (`tg_id`, username, `vless_uuid`)
- Set email (optional Remnawave UUID sync)
- Transaction history
- Send Telegram DM via bot API
- Open from Support tickets

---

## Transactions

**Route:** `/transactions`

Full payment history with server-side pagination, sort, and filters:

- Status (`created`, `confirmed`, `delivered`, `pending`, …)
- Payment method
- Date range
- Free-text search

Click a row for transaction detail (`transaction_id`, amount, days, tariff,
delivery status).

---

## Statistics

**Route:** `/stats`

Extended analytics beyond the home page:

- Same period KPIs
- Order status distribution (bar chart)
- Revenue and user growth charts

Revenue is converted to RUB using live CBR rates (with optional overrides in
`config.yml` — see [Configuration](configuration.md)).

---

## Promocodes

**Route:** `/promocodes`

Full guide: **[Referral & promocodes](referral.md)** (bonus credits / points wallet).

Two tabs:

### Codes

| Type | Behavior |
|------|----------|
| **Promotional** | Marketing code — redeemer gets bonus points immediately |
| **Referral** | User-owned invite code — owner earns points when invitees purchase |

List shows usage count, invitee days purchased, owner points rewarded, and
optional `credit_grant` override. Delete cascades redemption history.

### Settings

Stored in DB (`promo_settings`), not `config.yml`:

- `default_credit_grant` — points granted on redeem when code has no override
- `points_reward_per_30` — owner reward per 30 invitee-days
- `reward_cap_points` — cumulative owner reward cap

---

## CRM

**Route:** `/crm`

Marketing automation: segment users → Remnawave perks / bonus credits → Telegram
messages. Tabs: **Campaigns**, **Events** (UTC schedules), **History**.

Requires `redis` + `crm-worker`. Full guide: **[CRM](crm.md)**.

---

## Support

**Route:** `/support`

In-app support ticket inbox (replaces legacy support bot over time).

**Workflow:**

1. Filter by status: open / in_progress / closed
2. Open ticket drawer — read message thread
3. View image attachments (up to 3 per message, 5 MB each)
4. Reply with text + images → user notified via Telegram
5. Change ticket status
6. Delete own admin messages
7. Open linked user card from ticket

Attachments are stored in `./support_uploads` (shared mount between dashboard
and miniapp). See [Deployment](deployment.md#support-ticket-attachments).

---

## TG Admin

**Route:** `/tg-admin`

Telegram administration tools (requires `admin_bot_token`):

| Tool | Description |
|------|-------------|
| **Broadcast** | Mass DM to all non-banned users (~30 msg/s, background task) |
| **Channel post** | Post to news channel (`news_id`) with optional "Open bot" button |
| **FREE Sub Check** | Scan → find free Remnawave users not subscribed to channel → disable + notify |
| **Telemt Clean** | Scan → find free Telemt users not subscribed → delete + notify |

Scan/execute pattern: review candidates in a table, confirm with Popconfirm,
see results (disabled/deleted/notified/errors).

---

## Bot Constructor (legacy)

!!! note "Legacy mode"
    Disabled by default. Users are directed to the MiniApp for purchases.
    Enable in **WebApp → Settings** → `legacy_bot_constructor`, then restart bot.

When enabled, three additional pages appear:

### Tariffs

**Route:** `/tariffs`

Drag-and-drop tariff plan editor:

- Slug, names (RU/EN), duration days, discount %
- Squad profile binding
- Price matrix per payment method (Stars, Crypto, SBP, Crystal)
- Live Telegram preview by language and payment method

Changes bump `cache_version` — bot reloads tariffs automatically.

### Menus

**Route:** `/menus`

Inline Telegram menu builder:

- Screens with RU/EN message text
- Buttons: callbacks, URLs, visibility conditions
- Drag-and-drop button reorder
- Live Telegram preview panel

### Squads

**Route:** `/squads`

CRUD for Remnawave squad profiles:

- Name, `squad_id`, `external_squad_id`
- Referenced by legacy tariffs and WebApp invoice nodes
- Cannot delete if referenced (409)

---

## WebApp → Tariff Constructor

**Route:** `/webapp/tariffs`

**This is the primary way to configure purchases** for MiniApp, web portal, and
Android.

Build a **tree of menu nodes**:

| Node type (`action`) | Purpose |
|---------------------|---------|
| `buttons` | Navigation branch — contains child nodes |
| `invoice` | Purchasable leaf — triggers payment |

**Invoice node fields:**

| Field | Description |
|-------|-------------|
| Provider | Payment gateway (`apay`, `crystal`, `crypto`, `platega`, `paritypay`) |
| Amount | Price |
| Currency | `RUB`, `USDT`, etc. |
| Method | Sub-method (Platega: `2`=SBP; ParityPay: `sbp`/`card`) |
| Days | Subscription duration |
| Tariff slug | Encodes squad binding |

Provider list comes from `GET /api/webapp-menu/providers` — must match
`packages/payments` registry.

**Operations:**

- Create / edit / delete nodes
- Drag to reorder and reparent
- Toggle active/inactive
- Expand/collapse tree branches

Changes are live immediately — clients read `webapp_menu_nodes` on each request.

---

## WebApp → Settings

**Route:** `/webapp/settings`

| Setting | Effect |
|---------|--------|
| `legacy_bot_constructor` | Show/hide Bot Constructor nav group; requires bot restart |

---

## Telemt

**Route:** `/telemt`

Proxy to external Telemt server (`telemt_server` + `telemt_header`). Returns
503 if not configured.

Three tabs:

| Tab | Features |
|-----|----------|
| **Server** | System info, health, stats, runtime gates, security posture |
| **Users** | CRUD Telemt users (limits, expiry, traffic) |
| **Free Params** | DB-backed defaults for free Telemt access |

---

## Store

**Route:** `/store`

Proxy to external Store API (`store_url` + `store_api_token`). Hidden if not
configured.

Hierarchical editor for order parameters:

- `item_id` → `param_id` → `user_data_id` → params
- Types: days, hwid, location, internal_sq, external_sq

---

## API reference

All endpoints require `Authorization: Bearer <JWT>` unless noted.

| Router | Prefix | Key endpoints |
|--------|--------|---------------|
| Auth | `/api/auth` | `POST /login`, `GET /me` |
| Users | `/api/users` | list, detail, ban, VIP, send-message |
| Transactions | `/api/transactions` | list, detail, recent |
| Stats | `/api/stats` | summary, revenue, user-growth, payment-methods |
| Promos | `/api/promos` | CRUD, settings (credits / points) |
| CRM | `/api/crm` | segments, campaigns, events, evaluate |
| Tariffs | `/api/tariffs` | legacy plan CRUD + reorder |
| Menus | `/api/menus` | legacy screen/button CRUD |
| Squads | `/api/squads` | squad profile CRUD |
| Telemt | `/api/telemt` | proxy to Telemt API |
| Store | `/api/store` | proxy to Store API |
| Support | `/api/support` | tickets, reply, attachments |
| WebApp menu | `/api/webapp-menu` | tree CRUD, providers |
| Settings | `/api/settings` | feature flags |
| TG Admin | `/api/tg-admin` | broadcast, channel-post, clean tools |

Health check (unauthenticated): `GET /health`.

Swagger UI: set `expose_api_docs: true` in `config.yml` → `/bot/dashboard/api/docs`.

## UX patterns

- **Server-side pagination** on all tables
- **Debounced search** (400 ms) with request cancellation
- **Mobile-responsive** — card layouts and mobile sort controls on small screens
- **Unsaved changes warning** on tariff/menu editors
- **Dark liquid-glass theme** — `web/apps/dashboard/src/theme/`
