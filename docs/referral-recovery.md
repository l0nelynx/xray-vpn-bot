# One-time referral recovery

Dashboard → **TG Admin → Реферальные награды**.

## Deployment

Apply `0044_referral_recovery` after `0043_web_analytics` and deploy Bot, MiniApp
and Dashboard together. Stop old payment workers before migration and restart
the updated services afterward: mixing the old untracked reward path with the new
worker can double-count purchases. Complete or resolve old pending credit-paid
deliveries before confirming recovery.

The migration records existing completed transactions as `legacy`; the live
worker does not issue historical rewards automatically. Existing confirmed or
pending BONUS_CREDITS purchases are also reserved, because the old code could
award the owner before subscription delivery. New completed paid purchases are
processed independently of their UI/payment gateway with a receipt keyed by
transaction ID. The receipt and balance change are committed atomically. No
active subscription is required for the inviter.

Scope is the persisted `transactions` history. The optional Google Play IAP
handler currently uses a pseudo transaction ID and a separate
`google_play_purchases` table (latest state per token, not a complete purchase
ledger). Those purchases are not included in this operation or the transaction
worker; they require a separate integration and historical reconstruction.

## Calculation and review

1. Click **Рассчитать пропущенные награды**. This only stores a preview.
2. Review the current rate and cap, all recipients, previous owner rewards,
   manual grants, spending, balance, missing points and the 10% addition.
3. The base entitlement per referral code is
   `min(floor(total delivered invitee days / 30) * current rate, current cap)`.
   Only successful delivered paid purchases (including BONUS_CREDITS) after
   referral activation count. Refunded/cancelled, free and undelivered orders
   do not count. Email-only accounts use the synthetic identity where available.
4. Prior automatic rewards are the greater of the promo counter and ledger sum
   with `source=promo, reference=referral:<code>`. Differences are shown for review.
5. Positive `source=admin` entries are proposed as manual compensation, capped
   at the remaining entitlement. Review them; unrelated admin gifts must be
   excluded using **Зачесть вручную**, followed by recalculation. Spending is
   informational: spending promo activation grants must not reduce referral
   entitlement. Current balances cannot identify the source of spent points.
6. Bonus is `ceil(missing / 10)` per recipient, outside the referral cap. Fully
   compensated users receive no duplicate payment or apology notice.
7. Confirm the review checkbox, then the modal showing recipients and totals.
   Data changes after preview cause a conflict and require a new preview.

Historical rate/cap changes are not recorded, so the UI explicitly requires
approval of the current settings. Missing/ambiguous account mappings, missing
dates or payment amounts, multiple referral codes for one merged owner, and
old pending credit deliveries block execution and are listed with identifiers.
Resolve source data rather than guessing attribution. Legacy naive timestamps
are interpreted as UTC, consistently for both redemption and purchase dates;
verify boundary records if an older deployment stored a different timezone.

## Execution and report

All credits, manual-compensation counter reconciliation, transaction receipts,
notification outbox entries, approved snapshot and `executed` marker commit in
one DB transaction. A failure rolls back the whole issuance. Repeated confirmation
returns the saved result; a second recovery cannot issue more points.

The page reports the actual committed point totals and durable message counts.
Dashboard sends the apologies asynchronously, so closing the page is safe.
Successful Telegram responses count as sent, not read. Explicit rejections may
be retried from the page without reissuing points. Network uncertainty or a crash
after sending is marked `unknown` rather than blindly resent; inspect those
recipients manually. Recipients without Telegram ID still receive points and are
reported as `unavailable` for messaging.

Relevant tables: `referral_receipts`, `referral_recovery`, `referral_notices`,
`credit_ledger`. Base recovery grants use `referral:<code>`; the extra 10% uses
`source=referral_compensation` and `reference=recovery:<preview ID>`.
