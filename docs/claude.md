# Promo Code System — Reference (for refactoring)

End-to-end map of the promocode/referral system across `services/bot/`,
`services/miniapp/` and `services/dashboard/`, plus the shared `common_db` layer. Includes a
review of bugs, inconsistencies, security notes and dead/duplicated code.

> The promo system doubles as the **referral** system: every user's own
> `promo_code` is their referral code; activating someone else's code
> (`used_promo`) grants the activator a discount and the owner bonus days.

---

## 1. Data model

`packages/common_db/common_db/models/promos.py` — two tables (single source of truth,
re-exported by all three service shims):

### `promos`
| Column | Type | Meaning |
|---|---|---|
| `id` | PK | |
| `tg_id` | BigInteger, **unique** | Owner. One promo row per user. Manually-created promos use a **synthetic negative** tg_id. |
| `promo_code` | String(20), **unique** | The user's own/referral code. |
| `used_promo` | String(20), nullable | Code of *another* promo this user activated. NULL = none active. |
| `days_purchased` | Integer, default 0 | Total days bought by people who used this code (drives owner rewards). |
| `days_rewarded` | Integer, default 0 | Bonus days already granted to the owner (so rewards aren't double-counted). |
| `discount_percent` | Integer, nullable | Per-promo override. **NULL → fall back to PromoSettings.** `0` is a valid "no discount" override (distinct from NULL). |
| `used_promo_consumed` | Boolean, default False | True after the activated promo's discount was spent on a paid purchase. Owner's `used_promo` is kept (referral chain continues); only this flag flips. |

### `promo_settings` (singleton, id=1)
| Column | Meaning |
|---|---|
| `default_discount_percent` | Default used when a promo's `discount_percent` is NULL. Seeded to **20**. |

One row enforced via `common_db.repo.system.get_or_create_singleton`.

---

## 2. Shared logic — `common_db/repo/`

### `repo/promos.py`
- `get_promo_by_tg_id(session, tg_id)` — owner lookup.
- `get_promo_by_code(session, code)` — code lookup (empty string short-circuits to None).
- `get_effective_discount(session, tg_id) -> EffectiveDiscount | None` — **the canonical
  discount resolver.** Returns None unless the user has a promo, has an active
  `used_promo`, and `used_promo_consumed` is False. Cascade:
  `owner.discount_percent (if not NULL) → PromoSettings.default → 20 (auto-seed)`.

### `repo/system.py`
- `get_promo_settings` / `get_default_discount_percent` — singleton accessor, auto-seeds
  20% on a fresh DB so a missing row never silently yields 0%.

Tested by `tests/test_repo_promos.py` (cascade, NULL-vs-0, consumed, missing-owner,
fresh-DB seed) and `tests/test_repo_system.py`.

---

## 3. Where promos are created

| Path | Owner tg_id | Trigger |
|---|---|---|
| `app/handlers/base.py::invite_friends` | real user tg_id | User opens "Invite Friends"; `rq.create_promo` generates an 8-char A–Z0–9 code if none exists. |
| `app/database/requests.py::use_promo` | real user tg_id | If activator has no promo row yet, one is auto-created to hold `used_promo`. |
| `miniapp/backend/routers/promo.py::activate_promo` | real user tg_id | Same auto-create-on-activate, 8-char gen. |
| `dashboard/backend/routers/promos.py::create_promo` | **synthetic negative** (or explicit) | Admin creates a standalone marketing code. `owner_tg_id = min(min_tg_id, 0) - 1`. |

Code generation everywhere: `random.choices(ascii_uppercase + digits, k=8)` in a
`while True` loop checking uniqueness (relies on the unique constraint as backstop).

---

## 4. Where promos are activated (a user enters someone's code)

### Bot — `app/handlers/payments.py::process_promo_input`
1. `can_use_promo(tg_id)` gate (blocks if an active unconsumed promo exists).
2. `get_promo_by_code` existence check; reject own code.
3. `use_promo(tg_id, code)` sets `used_promo`, `used_promo_consumed=False`.
4. **Discount stored in FSM state from `secrets.get('promo_discount', 20)`** — a flat
   config value (see §7, issue A).

### MiniApp — `miniapp/backend/routers/promo.py::activate_promo`
- Stricter: rejects re-using the same code (409), rejects activating while another is
  active (409), rejects own code, 404 on unknown. Computes discount via the DB cascade.
- `GET /api/promo` returns `{can_activate, active_promo, discount_percent, default_discount_percent}`.

---

## 5. Where promos are consumed & rewards paid

All reward/consume logic lives in **`app/handlers/subscription_service.py`** (runs on
PAID delivery, in the bot process — including miniapp invoices, whose gateways confirm
via the bot's webhooks):

1. `get_promo_by_tg_id(buyer)` → if `used_promo` set:
2. `add_referral_days(used_promo, days)` bumps owner's `days_purchased`.
3. `reward_days = (days_purchased // 30) * promo_days_reward - already_rewarded`
   (`promo_days_reward` from **config.yml**, default 3).
4. If `reward_days > 0`: extend/upgrade the owner via Remnawave (PRO → add days;
   FREE → upgrade to PRO for reward_days), then `update_promo_days_rewarded`, notify owner.
5. `mark_promo_consumed(buyer)` flips `used_promo_consumed=True` (discount applies once).

Discount **application** to prices:
- Bot: `app/keyboards/tools.py` (`TariffButtonBuilder` / `OptimizedTariffKeyboard`)
  takes `extra_discount` (the FSM value) and multiplies `amount * (1 - extra_discount/100)`.
- MiniApp: `routers/payments.py::create_invoice` reduces the invoice amount via
  `get_effective_discount`; the frontend (`BuyMenuPage.tsx`) previews the discounted price.

---

## 6. Admin / dashboard surfaces

- **Bot admin** (`app/admin/promos.py`): paginated list, promo card (owner, days, invited
  users), delete with confirm. Reads via `app/database/requests.py`.
- **Dashboard** (`dashboard/backend/routers/promos.py` + `frontend/.../PromocodesPage.tsx`):
  `GET/POST /api/promos`, `DELETE /api/promos/{code}`, `GET/PUT /api/promos/settings`,
  `GET /api/promos/{code}/users`. Two tabs: Codes (CRUD) + Settings (default discount).
- Delete (both surfaces) nulls `used_promo` on users who activated the code, then deletes
  the row.

---

## 7. Findings — bugs, inconsistencies, security, dead code

### A. **Two divergent discount sources (highest priority)**
The **bot ignores the DB cascade**. `process_promo_input` and `invite_friends` use the
flat `secrets.get('promo_discount', 20)` / `promo_days_reward` from `config.yml`, while
**miniapp + dashboard** use `Promo.discount_percent` → `PromoSettings`. Consequence: the
*same* promo yields a different discount depending on whether the user buys via the bot
keyboard vs the miniapp, and a per-code `discount_percent` set in the dashboard has **no
effect on bot purchases**. The dashboard "Default discount" setting also does nothing for
the bot. Unifying on `get_effective_discount` is the core refactor.

### B. **Discount-window double-spend**
`used_promo_consumed` flips only at *delivery*, but the discount is granted at *invoice
creation* (miniapp) / *FSM entry* (bot). A user can create several discounted invoices
before any is delivered. Low monetary risk but real. Consider reserving/locking the promo
at invoice creation, or recomputing at delivery.

### C. **Bot activation is weaker than miniapp**
`process_promo_input` does not reject re-activating the *same* code, and `can_use_promo`
returns True whenever `used_promo is None` — so a user can keep swapping codes between
purchases. MiniApp enforces the stricter 409s. Behaviour should match after refactor.

### D. **Duplicated pagination query, with an off-by-one divergence**
`requests.py::get_promos_paginated` (0-based: `offset = page*per_page`) and
`dashboard/promos.py::list_promos` (1-based: `offset = (page-1)*per_page`) are otherwise
identical (same aliased `usage_count` subquery). Move to `common_db.repo.promos` and pick
one page convention. The bot admin list passes 0-based pages; the dashboard 1-based.

### E. **Reward arithmetic edge cases**
`(days_purchased // 30) * reward - already_rewarded` assumes `promo_days_reward` (config)
never changes; lowering it can make `reward_days` negative (guarded by `>0`, so no payout,
but `days_rewarded` then never reconciles). Also rewards are computed on `days` *ordered*,
not days actually delivered — a failed/partial delivery still credits the owner.

### F. **Delete loses history / referential gaps**
Deleting a promo removes the owner row entirely (its `days_purchased`/`days_rewarded`
history is gone) and nulls `used_promo` on activators, but does not reset their
`used_promo_consumed`. There are no FK constraints between `used_promo` and `promo_code`
(string match only), so "zombie" `used_promo` values are possible (handled gracefully by
the cascade, but worth modelling explicitly).

### G. **Synthetic-owner tg_id race**
`create_promo` computes `min(min_tg_id, 0) - 1` then inserts — two concurrent dashboard
creations can pick the same id and collide on the `tg_id` unique constraint (the second
500s instead of retrying). Minor.

### H. **Security (reviewed — mostly OK)**
- No SQL injection: all queries are parameterized SQLAlchemy.
- MiniApp endpoints are authenticated via Telegram `initData` HMAC with TTL + future-drift
  checks (`miniapp/backend/tg_auth.py`); dashboard via JWT.
- Promo codes are length/charset-bounded in pydantic (miniapp/dashboard) and uppercased.
  **The bot's `process_promo_input` has no length/charset bound** before lookup — harmless
  (parameterized) but inconsistent.
- Admin handlers re-check `is_admin` on every callback. Good.

### I. **Style/dead-code notes**
- `dashboard/promos.py::delete_promo` uses `Promo.__table__.update()` while
  `requests.py::delete_promo` uses `update(Promo)` — same effect, pick one.
- `requests.py` wrappers (`get_promo_by_code`, `get_promo_by_tg_id`) exist only to convert
  the ORM object to a dict for legacy bot callers; once handlers move to the repo +
  effective-discount API these dict shims can shrink.
- Two creation paths (`create_promo` vs auto-create inside `use_promo`) — consolidate.

---

## 8. Refactor checklist (suggested)

1. Replace bot's flat `promo_discount` with `get_effective_discount`; thread the resolved
   value (not a config constant) through `extra_discount`.
2. Decide one home for "default discount" and "reward days" — DB (`promo_settings`) is the
   better single source; migrate `promo_discount` / `promo_days_reward` out of config.yml.
3. Move pagination + activation rules into `common_db.repo.promos`; make bot and miniapp
   call the same functions (fixes A, C, D).
4. Close the double-spend window (B): consume/lock at invoice creation or recompute at
   delivery atomically.
5. Add a real link (or documented invariant) between `used_promo` and `promo_code`; define
   delete semantics (F).
