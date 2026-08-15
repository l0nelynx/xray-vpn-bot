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
| **Winner** | Result row after admin runs draw, linked to the concrete winning ticket |

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
- Re-draw a complete replacement set for a drawn giveaway; previous winners are excluded and the old result is preserved if there are too few candidates
- Open a branded, privacy-masked winner certificate and export one 1080×1350 PNG per eight winners (multiple pages download as ZIP)

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

Tickets receive stable display numbers `1…N` within their giveaway ordered by
`(created_at, id)`. Winner responses expose that value as `ticket_number`.
Random selection stores the actual weighted winning ticket; `most_tickets`
stores the participant's lowest-numbered ticket.

Draw and re-draw lock the giveaway row for the transaction. Re-draw replaces
the previous winner rows atomically and excludes only that immediately previous
set. `POST /giveaways/{id}/redraw` returns `409` without changing the result if
fewer than `winner_count` eligible participants remain.

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
