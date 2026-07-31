# Giveaways

Dashboard-managed raffles with bot participation, ticket tracking, and winner draw.
Rewards are **not** stored or issued by the system — admins distribute prizes manually.

**Source of truth:** `packages/common_db/common_db/repo/giveaways.py`

---

## Concepts

| Concept | Meaning |
|---------|---------|
| **Giveaway** | Campaign with entry rules, ticket mode, and winner selection |
| **Participant** | User who joined via bot (`?start=gw_{id}` or callback) |
| **Ticket** | Lottery entry weight; one row per granted ticket |
| **Winner** | Result row after admin runs draw |

### Schedule window

`starts_at` / `ends_at` are optional **UTC-naive** ISO timestamps (`YYYY-MM-DDTHH:MM:SS`).
Dashboard datetime inputs use the admin’s **local time** and convert to/from UTC on save/load.
Participation checks compare against `datetime.now(UTC)`. Empty bounds mean no limit.
Active giveaways can still update the schedule (dates only).

### Entry requirements (participant)

| Value | Behavior |
|-------|----------|
| `click_only` | User taps participate |
| `channel_sub` | User must be subscribed to `news_id` (checked via `getChatMember`) |

### Ticket sources (dynamic mode only)

| Source | Trigger |
|--------|---------|
| `join` | Successful entry (always 1 ticket) |
| `invitee_ref_activation` | Someone redeemed participant's referral code during active giveaway |
| `invitee_purchase` | Referred user completed a paid purchase during active giveaway |

Static mode: only the `join` ticket is granted.

---

## Surfaces

### Dashboard

**Route:** `/giveaways`

- Create / edit (draft only)
- Activate, close, bot broadcast, channel post
- View participants and ticket counts
- Draw winners (random weighted or most tickets)

API: `/bot/dashboard/api/giveaways/*`

### Bot

| Entry | Behavior |
|-------|----------|
| `?start=gw_{id}` | Join giveaway |
| `gw_join:{id}` | Inline button callback |
| `gw_subcheck:{id}` | Re-check channel subscription |

After join in dynamic mode with invitee sources, bot shows the user's referral deeplink.

---

## Data model

Tables: `giveaways`, `giveaway_participants`, `giveaway_tickets`, `giveaway_winners`.

`giveaways.config_json`:

```json
{
  "distribution": ["bot", "channel"],
  "entry_condition": "click_only",
  "ticket_sources": ["invitee_ref_activation", "invitee_purchase"],
  "chance_mode": "dynamic",
  "winner_selection": "random"
}
```

---

## Related

- [Referral](referral.md) — referral stats tab in Promocodes; invitee ticket hooks use `promo_redemptions`
- [Dashboard](dashboard.md)
