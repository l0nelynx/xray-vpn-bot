# External Integrations

## VPN panel: Remnawave

Subscriptions are provisioned through the **Remnawave** panel via the
`remnawave_client` package (single client shared by the bot and miniapp):
create/extend/update users, reset traffic, fetch VLESS subscription links,
list/delete HWID devices. Users are assigned to Remnawave **squads**; a tariff's
`squad_id` selects the squad. Config: `remnawave_url`, `remnawave_token` (and the
free squad id) in `config.yml`.

## Payments

Gateway logic is centralised in `packages/payments`:
- **Providers** (`apay`, `crystal`, `crypto`, `platega`) — create a hosted
  invoice from a provider-agnostic `InvoiceRequest`.
- **Signatures** (`payments.signatures`) — verify each gateway's webhook
  (APay md5, CrystalPay sha1, CryptoBot HMAC-SHA256, Platega header check).

Credentials are injected per service via `set_config_provider`. Flow: a client
(bot or miniapp) creates an invoice → the user pays → the gateway calls the
bot's `/bot/*_webhook` endpoint → the signature is verified → the subscription is
delivered (and the transaction marked `delivered`).

Also supported: **Telegram Stars** (native Telegram invoices handled in the bot)
and **Google Play IAP** (Android; verified via `google-api-python-client`, see
[android-api.md](android-api.md)).

## Server monitoring: Telemt

**Telemt** exposes VPN-server health/usage; the Dashboard surfaces CPU/RAM,
connections and traffic and can manage host/server state. Config: `telemt_*`
(server URL + auth header) in `config.yml`.
