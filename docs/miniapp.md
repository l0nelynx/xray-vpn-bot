# Telegram MiniApp

The project includes a Telegram MiniApp (TWA) to provide a more interactive and visually appealing interface for users directly within the Telegram app.

## Components

-   **Backend (`miniapp/backend/`)**: A FastAPI application that provides the API endpoints for the MiniApp.
-   **Frontend (`miniapp/frontend/`)**: A React-based Single Page Application (SPA).

## Core Modules

-   **`devices`**: Handles user devices and configuration.
-   **`free`**: Manages free trial or free tier subscriptions.
-   **`me`**: User profile and status information.
-   **`menu`**: Provides the data for the dynamic menu system.
-   **`payments`**: Handles payment requests and transaction status checks from the MiniApp.
-   **`promo`**: Logic for applying and viewing promo code status.
-   **`support`**: Integrated support ticket system within the MiniApp.

## Functionality

The MiniApp allows users to:
-   Browse and select VPN tariffs in a graphical interface.
-   Manage their active subscriptions.
-   Contact support and view ticket history.
-   Apply promo codes.
-   View connection instructions and download configurations.

## Integration

The MiniApp is typically launched from the Seller Bot via a "Web App" button. It communicates with its own backend, which in turn interacts with the shared SQLite database and the Remnawave API.

## Technical Stack

-   **Backend**: FastAPI, SQLAlchemy.
-   **Frontend**: React, Vite, Tailwind CSS, Telegram WebApps SDK.
