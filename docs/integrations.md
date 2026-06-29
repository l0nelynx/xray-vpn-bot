# External Integrations

The XRAY-VPN-BOT integrates with several external services to provide VPN functionality, payment processing, and server monitoring.

## VPN Panel: Remnawave

The bot uses the **Remnawave** API to manage VPN subscriptions. Integration is handled by the `remnawave_client` package.

-   **Purpose**: Creating users, extending subscriptions, and retrieving connection configurations (VLESS).
-   **Configuration**: Requires `remnawave_url` and `remnawave_token` in `config.yml`.
-   **Squads**: Users are assigned to "Squads" in Remnawave. The IDs for free and pro squads are defined in the configuration.

## Payment Gateways

The bot supports multiple payment methods, each integrated via its respective API and webhook system.

### 1. Telegram Stars
-   **Purpose**: Built-in Telegram payment system.
-   **Workflow**: The bot generates an invoice, and Telegram handles the payment. Confirmation is received via `PreCheckoutQuery` and `SuccessfulPayment` events.

### 2. CryptoBot
-   **Purpose**: Cryptocurrency payments (USDT, TON, BTC, etc.).
-   **Workflow**: The bot creates an invoice via the CryptoBot API. Confirmation is received through webhooks.

### 3. Crystal Pay
-   **Purpose**: Aggregate payment provider (supports cards, e-wallets, crypto).
-   **Workflow**: Users are redirected to Crystal Pay's checkout page. Status updates are sent to the bot's FastAPI webhook endpoint.

### 4. A-Pays
-   **Purpose**: Payment gateway primarily for RUB/SBP transactions.
-   **Workflow**: Similar to Crystal Pay, using merchant IDs and secret keys for verification.

## Server Monitoring: Telemt

**Telemt** is used to monitor the health and resource usage of the VPN servers.

-   **Features**: View CPU/RAM usage, active connections, and traffic statistics directly in the Dashboard.
-   **Configuration**: Requires `telemt_server` URL and `telemt_header` for authorization.
