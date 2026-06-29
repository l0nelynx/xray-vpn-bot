# Seller Bot

The Seller Bot is the core of the XRAY-VPN-BOT project. It is responsible for interacting with users, managing subscriptions, and processing payments.

## Directory Structure (`app/`)

-   `admin/`: Contains logic for the admin interface within Telegram (broadcasts, user management, migrations).
-   `api/`: Clients for external services:
    -   `a_pay.py`, `crystal_pay.py`, `crypto_pay.py`: Payment gateway integrations.
    -   `remnawave/`: Integration with the Remnawave VPN panel.
    -   `telemt.py`: Integration with Telemt for server health monitoring.
-   `database/`: Database models (`models.py`) and session management.
-   `handlers/`: Aiogram handlers for various bot events (commands, callbacks).
-   `keyboards/`: Inline and reply keyboard definitions.
-   `locale/`: Internationalization files (English and Russian).
-   `marzban/`: Legacy code for Marzban panel migration.
-   `settings.py`: Configuration loading and global settings.
-   `tariffs.py`: Helpers for managing VPN tariff plans.

## Core Functionality

### 1. Subscription Management
The bot allows users to:
-   View available VPN plans.
-   Purchase subscriptions using various payment methods.
-   Check their current subscription status and expiration date.
-   Get connection details (VLESS links).

### 2. Payment Processing
The bot uses **FastAPI** to listen for webhooks from payment providers. When a payment is confirmed:
1.  The transaction is recorded in the database.
2.  The user's subscription is created or extended in the **Remnawave** panel.
3.  The user receives a notification in Telegram.

### 3. Admin Capabilities
Administrators can:
-   Send broadcast messages to all users.
-   Ban/unban users.
-   View logs and system statistics.
-   Manage migrations.

## Entry Point

The main entry point for the Seller Bot is `main.py` in the project root. It initializes the `aiogram` dispatcher, starts the FastAPI server for webhooks, and sets up the database.

## Dependencies
- `aiogram`: Telegram Bot API framework.
- `SQLAlchemy`: ORM for database interactions.
- `FastAPI`: Web framework for payment webhooks.
- `uvicorn`: ASGI server for FastAPI.
