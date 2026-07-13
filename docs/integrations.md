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

Gateway logic is centralised in `packages/payments`:
- **Providers** (`apay`, `crystal`, `crypto`, `platega`, `paritypay`) — create a
  hosted invoice from a provider-agnostic `InvoiceRequest`.
- **Signatures** (`payments.signatures`) — verify each gateway's webhook
  (APay md5, CrystalPay sha1, CryptoBot HMAC-SHA256, Platega header check,
  ParityPay HMAC-SHA256).

Credentials are injected per service via `set_config_provider`. Flow: a client
(MiniApp, web portal, Android, or legacy bot) creates an invoice with **`node_id`
only** (server reads price from `webapp_menu_nodes`) → the user pays → the gateway
calls the bot's `/bot/*_webhook` endpoint → the signature is verified → the
subscription is delivered (and the transaction marked `delivered`).

Also supported: **Telegram Stars** (native Telegram invoices handled in the bot)
and **Google Play IAP** (Android; verified via `google-api-python-client`, see
[android-api.md](android-api.md)).

## Server monitoring: Telemt

**Telemt** exposes VPN-server health/usage; the Dashboard surfaces CPU/RAM,
connections and traffic and can manage host/server state. Config: `telemt_*`
(server URL + auth header) in `config.yml`.
