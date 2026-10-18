# Remnawave availability

The MiniApp API runs a monitor in its FastAPI lifespan. It uses a hybrid strategy:

- An authenticated `GET /users/stream?size=1` through the configured Remnawave SDK
  every 60 seconds detects outages even when nobody opens the MiniApp. The probe
  has a five-second timeout and exercises the API, authentication and panel DB.
- Transport errors, timeouts, HTTP 401/403/408 and 5xx from real MiniApp API
  operations record an incident immediately, even if the shared client returns
  `None` for compatibility. Business errors, genuine 404s and request rate limits
  do not open an incident.
- During an incident, probes run every 15 seconds. Only a successful probe closes
  it. The scheduler wakes at most every five seconds, so an idle-worker probe can
  start up to five seconds after its scheduled time.

The administrator receives outage and recovery messages through `admin_bot_token`
to `admin_id`, matching the existing new-ticket notification route. There is one
notice per transition; repeated failed requests do not create repeated alerts.
This monitoring is independent of the dashboard's optional API-health alerts.

The Telegram MiniApp polls the local availability endpoint every 15 seconds and
shows a maintenance banner with an explicit recovery-notification opt-in. The
authenticated `POST /api/remnawave/recovery-notification` accepts the UI language;
the recipient is always derived from signed Telegram init data. Repeated opt-ins
are idempotent. After recovery, opted-in users receive a message from the main
bot (`token`). Subscriptions apply to the current incident only. An open MiniApp
refreshes its account information when it observes recovery.

Migration `0045_remnawave_availability` adds the singleton availability row,
recovery subscriptions and a pending-notice queue. They survive service restarts.
PostgreSQL row locks serialize transitions and probes across API workers;
`SKIP LOCKED` claims pending notices. Telegram delivery runs in a separate task,
prioritizes admin notices and retries failed deliveries after 30 seconds. A
blocked/deleted user is removed from the queue. As with any Telegram send API
without idempotency keys, a crash after Telegram accepts a message but before DB
commit can cause a repeated delivery.

Deploy the updated MiniApp API, frontend and shared packages together. Normal
service startup applies the migration. No new credentials or settings are needed.
Keep the MiniApp API running for background detection and recovery delivery.

Validation:

```text
python -m pytest tests/test_remnawave_availability.py tests/test_migration_heads.py
npm run build --workspace=xray-vpn-miniapp
npm run preview --workspace=xray-vpn-miniapp -- --port 5178
node scripts/test-miniapp-maintenance.mjs
```
