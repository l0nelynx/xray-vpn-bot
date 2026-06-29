# Admin Dashboard

The Admin Dashboard is a web-based interface that allows administrators to manage the XRAY-VPN-BOT system without interacting directly with the database or code.

## Architecture

The dashboard is split into two main parts:
1.  **Backend (`dashboard/backend/`)**: A FastAPI application that serves as the API for the frontend. It handles authentication, data retrieval, and modification.
2.  **Frontend (`dashboard/frontend/`)**: A Single Page Application (SPA) built with React and Vite. It provides a modern UI for administrative tasks.

## Key Features

### 1. Tariff Constructor
Administrators can create, edit, and delete VPN subscription plans (tariffs). Features include:
-   Setting prices in different currencies (Telegram Stars, USDT, RUB).
-   Defining subscription duration (days).
-   Assigning specific Remnawave squads to tariffs.
-   Reordering plans via a drag-and-drop interface.

### 2. Menu Builder
A powerful tool to design the bot's inline menus:
-   Create nested menu structures.
-   Add buttons with custom text and actions (links, invoice generation).
-   Live editing that propagates to the bot immediately.

### 3. User Management
-   Browse the list of registered users.
-   View user details, including their VLESS UUID and subscription status.
-   Ban or unban users.

### 4. Transaction & Stats
-   View a history of all payment transactions.
-   Monitor sales statistics and revenue.
-   Track traffic usage (if integrated with Telemt).

### 5. Promo Codes
-   Manage promotional codes.
-   Set discount percentages and bonus days.

### 6. Telemt Integration
-   Monitor the health and system info of the Telemt server.
-   Manage server state directly from the dashboard.

## Authentication

The dashboard uses JWT (JSON Web Token) for authentication. Credentials (`dashboard_login` and `dashboard_password`) are defined in `config.yml`. The `dashboard_secret` is used to sign the tokens.

## Deployment

The dashboard is packaged as a Docker container.
-   **Internal Port**: 8000 (FastAPI).
-   **Typical Host Port**: 8080 (mapped in `docker-compose.yml`).

The frontend is built and served as static files by the FastAPI backend.
