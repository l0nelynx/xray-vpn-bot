# Project Architecture

The XRAY-VPN-BOT project is a comprehensive suite for selling and managing VPN subscriptions via Telegram. It is composed of several interconnected services orchestrated via Docker Compose.

## Components Overview

1.  **Seller Bot (Main Bot)**:
    *   **Path**: `./app/`, `main.py`
    *   **Role**: The primary user interface for customers. Handles plan selection, payments, and subscription management.
    *   **Tech Stack**: Python, `aiogram` 3.x, `SQLAlchemy`, `FastAPI` (for webhooks).

2.  **Support Bot**:
    *   **Path**: `support.py`
    *   **Role**: Facilitates communication between users and administrators. Handles support tickets and direct messaging.
    *   **Tech Stack**: Python, `aiogram` 3.x.

3.  **Dashboard**:
    *   **Path**: `./dashboard/`
    *   **Role**: Administrative web interface for managing tariffs, menus, users, and viewing statistics.
    *   **Tech Stack**:
        *   **Backend**: FastAPI, JWT authentication.
        *   **Frontend**: React + Vite, Tailwind CSS.

4.  **MiniApp**:
    *   **Path**: `./miniapp/`
    *   **Role**: A Telegram MiniApp integrated into the bot for a richer UI experience during selection and support.
    *   **Tech Stack**:
        *   **Backend**: FastAPI.
        *   **Frontend**: React + Vite.

5.  **Remnawave Client**:
    *   **Path**: `./packages/remnawave_client/`
    *   **Role**: A shared library for interacting with the Remnawave VPN panel API.

## Data Flow

*   **User Action**: A user interacts with the Seller Bot or MiniApp.
*   **Database**: All services share a common SQLite database (`db.sqlite3`), ensuring data consistency across the bot, dashboard, and miniapp.
*   **VPN Management**: The Seller Bot communicates with the **Remnawave** panel to create/extend VPN accounts using the `remnawave_client`.
*   **Payments**: External payment gateways (CryptoBot, Crystal Pay, A-Pays) send webhooks to the Seller Bot's FastAPI endpoints to confirm transactions.
*   **Administration**: Admins use the Dashboard to modify tariffs or the Support Bot to respond to user inquiries.

## Deployment

The project is designed to run in Docker containers. A `docker-compose.yml` file defines the services:
*   `seller-bot`: Main bot and payment webhooks.
*   `support-bot`: Dedicated support messaging.
*   `dashboard`: The web admin interface.

The `miniapp` is typically served via the same backend as the dashboard or bot, depending on the configuration.
