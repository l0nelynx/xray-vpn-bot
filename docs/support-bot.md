# Support Bot

The Support Bot is a standalone Telegram bot designed to facilitate communication between users and administrators. It allows users to send messages, photos, documents, and videos to the administration team and receive replies directly within the bot.

## Core Features

-   **Two-way Communication**: Users can message the bot, and admins can reply to those messages.
-   **Media Support**: Supports text, photos, documents, and videos.
-   **Admin-Only Access**: Certain features and the ability to reply are restricted to administrators (defined in `config.yml`).
-   **Session State**: Uses Aiogram's Finite State Machine (FSM) to handle the reply process.

## How it Works

1.  **User Inquiry**: A user sends a message to the Support Bot.
2.  **Forwarding to Admin**: The bot forwards the user's message to the administrator(s). The forwarded message includes an "Answer" button.
3.  **Admin Reply**:
    -   The admin clicks the "Answer" button.
    -   The bot enters a "waiting for reply" state for that specific user.
    -   The admin sends their response (text or media).
    -   The bot sends the admin's response back to the user.

## Implementation Details

-   **Entry Point**: `support.py` in the project root.
-   **Configuration**: Loads settings from `config.yml` (e.g., `support_token`, `admin_id`).
-   **Database**: Uses `support_db.py` for managing support-related data (if applicable) and shares the main `db.sqlite3`.
-   **Framework**: Built with `aiogram` 3.x.

## Commands

-   `/start`: Initializes the bot for the user and provides a welcome message.

## Admin Controls

Administrators are identified by their Telegram ID in the configuration. They receive all user messages and can use the inline "Answer" button to initiate a reply.
