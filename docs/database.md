# Database Schema

The project uses a shared SQLite database (`db.sqlite3`) to store all application data. The schema is managed using SQLAlchemy ORM.

## Main Tables

### `users`
Stores information about Telegram users and their VPN profiles.
- `id`: Internal primary key.
- `tg_id`: Telegram User ID (unique).
- `username`: Telegram username.
- `vless_uuid`: The UUID assigned to the user in the VPN panel.
- `api_provider`: The VPN panel provider (e.g., "remnawave").
- `email`: User email (often used as the identifier in Remnawave).
- `is_banned`: Boolean flag for user access.
- `language`: User's preferred language (en/ru).
- `vip`: Integer flag for VIP status.

### `transactions`
Records all payment attempts and completed orders.
- `transaction_id`: External ID from the payment provider.
- `vless_uuid`: User's VPN UUID.
- `order_status`: Current status (e.g., "paid", "pending").
- `payment_method`: Provider used (e.g., "cryptobot", "stars").
- `amount`: Transaction amount.
- `days_ordered`: Duration of the purchased subscription.
- `tariff_slug`: Identifier of the purchased tariff.

### `tariff_plans`
Defines the available VPN subscription plans.
- `name`: Display name.
- `slug`: Unique identifier.
- `duration_days`: Plan length.
- `is_active`: Visibility toggle.
- `squad_id`: The Remnawave squad assigned to this plan.

### `tariff_prices`
Stores pricing for tariffs in different currencies.
- `tariff_id`: Link to `tariff_plans`.
- `currency`: e.g., "stars", "usdt", "rub".
- `amount`: The price value.

### `promos`
Manages promotional codes and rewards.
- `promo_code`: The code string.
- `discount_percent`: Percentage discount.
- `days_rewarded`: Extra days granted.

### `support_tickets` & `support_messages`
Handles support interactions.
- `subject`: Ticket topic.
- `message`: Initial user message.
- `status`: "open", "closed", etc.
- `messages`: Individual replies between user and admin.

### `webapp_menu_nodes`
Stores the dynamic menu structure configured in the Dashboard.
- `parent_id`: For nested menus.
- `text`: Button label.
- `action`: Type of action (e.g., "link", "buttons", "invoice").

## Migration & Initialization
The database is automatically initialized and migrated on startup in `app/database/models.py` (for the bot) and `miniapp/backend/main.py` (for the miniapp). It checks for missing columns and tables to ensure the schema matches the current version of the code.
