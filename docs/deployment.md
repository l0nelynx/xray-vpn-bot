# Deployment and Configuration

The XRAY-VPN-BOT is designed for containerized deployment using Docker and Docker Compose. This ensures a consistent environment for all components.

## Prerequisites

-   Docker and Docker Compose installed on the host machine.
-   A Telegram Bot token (from @BotFather).
-   A Remnawave API token.
-   (Optional) Credentials for payment gateways (CryptoBot, Crystal Pay, etc.).

## Configuration (`config.yml`)

1.  Copy the example configuration: `cp config-example.yml config.yml`.
2.  Edit `config.yml` with your specific settings.
    -   **Branding**: Set your service name and links.
    -   **Tokens**: Enter your Telegram bot tokens (main, support, admin).
    -   **Remnawave**: Provide the URL and API token for your panel.
    -   **Dashboard**: Set the login, password, and a random secret for JWT.
    -   **Payments**: Add API keys for any payment gateways you wish to use.

## Deployment with Docker Compose

The `docker-compose.yml` file defines three services:

1.  **`seller-bot`**: Runs the main bot and the FastAPI server for payment webhooks.
    -   **Ports**: Maps internal `5000` to host `5000`.
2.  **`support-bot`**: Runs the standalone support bot.
3.  **`dashboard`**: Runs the admin dashboard backend and serves the frontend.
    -   **Ports**: Maps internal `8000` to host `8080`.

### Initial Setup

```bash
# Create the database directory and file
mkdir -p db
touch db/db.sqlite3

# Create the external network (if required by your setup)
docker network create backend-network
```

### Launching

```bash
# Build and start the containers
docker compose up -d --build
```

## Reverse Proxy

It is highly recommended to run the services behind a reverse proxy like **Nginx**, **Caddy**, or **Traefik**. The proxy should:
-   Terminate TLS (HTTPS).
-   Forward traffic to the Seller Bot (webhook endpoints) and the Dashboard.
-   Handle domain-based routing.

## Local Development (Non-Docker)

To run the bot locally without Docker:
1.  Create a virtual environment: `python -m venv venv`.
2.  Activate it: `source venv/bin/activate` (or `venv\Scripts\activate` on Windows).
3.  Install dependencies: `pip install -r requirements.txt`.
4.  Run the bot: `python main.py`.
5.  Run the support bot: `python support.py`.
