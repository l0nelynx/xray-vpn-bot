# GA4 purchases from the web portal

An administrator can enable **Dashboard → Settings → Analytics → Google Analytics 4**.
Use the Measurement ID configured as `VITE_GA_ID` in the portal. Create an API
secret in Google Analytics → Admin → Data streams → the same web stream →
Measurement Protocol API secrets.

The Dashboard stores the settings in the encrypted `app_integrations` record for
`ga4`. The form shows whether a secret is set. Leave it blank to keep the
current secret or enter a replacement to rotate it. The existing runtime settings
poller propagates changes to the miniapp. The worker checks the configuration on
each batch. Disabling pauses delivery and stops adding new invoices to the queue.

## Release

Deploy the frontend, Dashboard, bot and miniapp from the same revision. The
standard migration job must reach `0049_web_payment_confirmation` before the
updated services start. Subsequent GA4 settings changes take effect at runtime.

## Events and delivery

The web invoice endpoint accepts optional `analytics.client_id` and
`analytics.session_id`. Missing or invalid IDs skip analytics for that invoice.
The outbox stores the IDs and payment provider, keyed by the local transaction ID.
A queue write failure leaves the invoice usable.

The bot records the first verified payment time in `transactions.payment_confirmed_at`.
Subscription delivery proceeds independently. The miniapp builds the purchase
from the confirmed transaction, including its amount, invoice currency, tariff
snapshot and renewal target. Credits use the portal's existing frontend events.
For CryptoPay invoices denominated in tokens, the purchase includes the settled
`payment_amount` and `payment_asset` as custom parameters. GA4 monetary revenue
uses ISO 4217 currencies and requires a verified fiat amount.

The worker polls every 15 seconds. It reserves each outbox row before making the
HTTP request and records the result in `attempts`, `last_error`, `next_attempt_at`
and `sent_at`. The database releases its locks before the network call.
Network and HTTP errors are retried with backoff for up to 71 hours after payment.
Expired rows remain available for inspection. Repeated webhooks share one row.
If the worker stops after Google accepts the event but before saving the result,
it retries with the original transaction ID and timestamp for GA4 deduplication.

## Verification

Run `python -m pytest tests/test_ga4_dashboard_settings.py tests/test_web_analytics.py tests/test_payment_delivery_retry.py tests/test_migration_heads.py`.
The checkout test uses a local HTTP collector and exercises a failed delivery,
a concurrent worker and a repeated payment notification. A live property's
reports require separate verification because the collection endpoint returns
HTTP 2xx on receipt. [Google Measurement Protocol reference](https://developers.google.com/analytics/devguides/collection/protocol/ga4/reference)
