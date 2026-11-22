# Support workflow

Dashboard uses a queue and conversation layout. Tickets needing a reply are
ordered by the start of the current wait, oldest first. Reading a ticket does
not remove it from this queue. Public replies move it to `waiting_user`; user
messages move it to `open`. `in_progress` remains available for investigation.
Internal notes never affect reply ownership or public previews, and their
attachments cannot be downloaded through user endpoints.

Users can resolve a ticket and reopen it within seven days of closure. The
five-ticket limit includes all active statuses. Telegram and Android routes
share the same transitions, read cursors, context and attachment checks. The
Telegram support chat uses the same tickets and uploads as these clients.

## Telegram support chat

Set `support_token` to a separate Telegram bot token in `config.yml`. The
`bot` service polls it alongside the seller bot when connected to PostgreSQL. Starting a private chat
registers the Telegram account and opens the ticket menu in Russian or English.
Users can include an order number, purchase email or subscription link in the
description. These are optional details for the operator. Account linking uses
the existing verified linking flow.

Users choose a category, enter a description (or photo caption), attach up to
three images and tap Send. Drafts live in memory until submission or restart.
Operators work in Dashboard. Their notifications contain the ticket number and
Dashboard link. After a user writes through the support bot, public replies
arrive in that chat with a button to view the thread and download its images.

## Deployment

When upgrading from the standalone bot, stop its container first
(`docker stop support-bot` if it is running). Keep `db/support_bot.sqlite3`
as an offline archive. The new bot does not mount, read or import it. Use images from the same release and run the normal Compose
upgrade. The `migrate` service applies `0050_support_reply_channel` before
the new bot starts. Mount `./support_uploads:/app/support_uploads` read-write
for bot, miniapp and dashboard, with host directory ownership 10001:10001.

Apply Alembic revision `0041_support_workflow` before deploying the updated
API. It adds workflow fields and normalizes old timestamps to UTC. Historical
timestamps without an offset are interpreted as UTC by default, matching the
default Docker timezone. If the old dashboard used another timezone, set
`SUPPORT_LEGACY_TIMEZONE` when running this migration (for example `+03:00` or
`Europe/Minsk`). Named zones require the operating system timezone database.
No live database migration is performed by the frontend preview.

Notification links use `miniapp_url` and optionally `dashboard_url`. If the
latter is absent, the dashboard link uses `/bot/dashboard` on the miniapp
origin. Only HTTPS links are emitted. Delivery checks Telegram's response and
retries transient failures up to three times; failures are logged without bot
tokens. These are bounded in-process retries, not a durable notification queue.

Read cursors are shared by the support team; assignment uses the existing
authenticated dashboard login. This does not add a new administrator account
management system. Templates are editable before sending and saved in the
current browser. Text drafts live in session storage; photos must be reselected
after leaving a conversation or form.

## Local interactive preview

Run `npm run dev:support` from the repository root. It starts:

- Dashboard: http://127.0.0.1:5173/bot/dashboard/support
- Miniapp: http://127.0.0.1:5174/bot/miniapp/support?mock=default-ru
- Shared support mock API: http://127.0.0.1:8790/health

Use any nonempty login and password in the mock dashboard, such as `admin` /
`admin`. No Telegram login is needed for the miniapp. Support data and uploaded
images are held in memory and shared between the two apps. Restarting the API
restores four sample tickets; it never contacts Telegram or the production DB.
Other screens continue using the existing MSW fixtures. The mock API is bound
to loopback only and deliberately has no production authentication.

To run the browser verification against a fresh preview, use
`node scripts/verify-support-ui.mjs`. It changes only the in-memory sample data,
checks cross-app replies, drafts, notes, closure/reopening and first-message
photos, and writes review screenshots under `docs/screenshots/support-workflow`.

Backend regression coverage lives in `tests/test_support_workflow_api.py` and
`packages/common_db/tests/test_support_*`. To run the Telegram integration tests,
set `SUPPORT_TEST_POSTGRES_URL` to an asyncpg URL for a disposable PostgreSQL
16 database and run `python -m pytest tests/test_telegram_support.py`. The tests
create temporary schemas and simulate Telegram updates and delivery.
