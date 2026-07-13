# External Integrations

## VPN panel: Remnawave

Subscriptions are provisioned through the **Remnawave** panel via the
`remnawave_client` package (single client shared by the bot and miniapp):
create/extend/update users, reset traffic, fetch VLESS subscription links,
list/delete HWID devices. Users are assigned to Remnawave **squads**; a tariff's
`squad_id` selects the squad. Config: `remnawave_url`, `remnawave_token` (and the
free squad id) in `config.yml`.

### Inbound webhooks (torrent blocker)

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

When `scope=torrent_blocker` and `event=torrent_blocker.report` with an active
block, the bot looks up the local user by `data.user.uuid` → `users.vless_uuid`
and sends a localized Telegram warning (at most once per user per 24 hours).

Other scopes are acknowledged with HTTP 200 but not processed.

## Payments

Payment gateway setup, built-in providers, webhook routing, and a step-by-step
guide for adding custom gateways are documented in
**[Payment gateways](payment-gateways.md)**.

Quick summary: clients create invoices with **`node_id` only** → user pays at the
gateway → bot verifies webhook signature → subscription delivered via Remnawave.

Also supported outside `packages/payments`: **Telegram Stars** (legacy bot) and
**Google Play IAP** (Android — see [android-api.md](android-api.md)).

## Server monitoring: Telemt

**Telemt** exposes VPN-server health/usage; the Dashboard surfaces CPU/RAM,
connections and traffic and can manage host/server state. Config: `telemt_*`
(server URL + auth header) in `config.yml`.
