# External Integrations

## VPN panel: Remnawave

Subscriptions are provisioned through the **Remnawave** panel via the
`remnawave_client` package (single client shared by the bot and miniapp):
create/extend/update users, reset traffic, fetch VLESS subscription links,
list/delete HWID devices. Users are assigned to Remnawave **squads**; a tariff's
`squad_id` selects the squad. Config: `remnawave_url`, `remnawave_token` (and the
free squad id) in `config.yml`.

### Inbound webhooks (CRM rules)

The seller bot accepts panel webhooks at `POST /bot/remnawave_webhook`.
Parsing and signature verification live in `packages/remnawave_client/remnawave_client/webhooks.py`.

**Bot config** (`config.yml`):

```yaml
remnawave_webhook_secret: "<same value as panel WEBHOOK_SECRET_HEADER>"
```

Generate a secret (letters and digits only, as required by the panel):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Panel `.env`:**

```bash
WEBHOOK_ENABLED=true
WEBHOOK_URL=https://your-domain/bot/remnawave_webhook
WEBHOOK_SECRET_HEADER=<same secret as remnawave_webhook_secret>
```

After HMAC verification the bot **acks immediately** and enqueues the payload to
Redis (`execute_crm_webhook`). The `crm-worker` matches enabled rules from
Dashboard → CRM → **Webhooks** by `scope` + `event`, resolves the local user
(`vless_uuid` / `telegramId`), and runs the same CRM actions as campaigns
(messages, Remnawave perks, credits).

Supported scopes for rules: `user`, `torrent_blocker`, `user_hwid_devices`.
Other Remnawave scopes are acknowledged with HTTP 200 but match no rules.

Configure torrent warnings (and other events) in the Webhooks tab — there is no
hardcoded torrent message anymore. Optional per-rule `cooldown_hours` limits
repeat sends to the same user.

Webhook-only message variables: `{{notConnectedAfterHours}}`, `{{deviceModel}}`,
`{{platform}}`, `{{osVersion}}`, `{{ip}}`, `{{blockMinutes}}` (plus the usual CRM
placeholders).

## Payments

Payment gateway setup, built-in providers, webhook routing, and a step-by-step
guide for adding custom gateways are documented in
**[Payment gateways](payment-gateways.md)**.

Quick summary: clients create invoices with **`node_id` only** → user pays at the
gateway → bot verifies webhook signature → subscription delivered via Remnawave.

The payments registry also exposes **Telegram Stars** to Telegram Bot and
MiniApp only. **Google Play IAP** remains an Android-specific integration (see
[android-api.md](android-api.md)).

**FCM push** (Android): clients register device tokens via `/api/android/fcm`;
operators send campaigns from Dashboard → **Push**. Config: `fcm_project_id`,
`fcm_service_account_path` (readable by `dashboard` and `crm-worker`).

## Server monitoring: Telemt

**Telemt** exposes VPN-server health/usage; the Dashboard surfaces CPU/RAM,
connections and traffic and can manage host/server state. Config: `telemt_*`
(server URL + auth header) in `config.yml`.
