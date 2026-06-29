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

The `docker-compose.yml` file defines six services:

1.  **`postgres`**: PostgreSQL 16 (alpine). Data lives in `./pg_data`. Healthchecked via `pg_isready`. Not exposed to the host — only reachable on the `backend-network`.
2.  **`migrate`**: One-shot init container. Runs Alembic `upgrade head` against `DATABASE_URL`, then exits. `restart: "no"`. App services wait on `service_completed_successfully` before starting.
3.  **`seller-bot`**: Main bot + FastAPI server for payment webhooks. **Ports**: `127.0.0.1:5000 → 5000`.
4.  **`miniapp`**: Telegram WebApp + Android API backend. Internal port `8001`, exposed through the seller-bot proxy.
5.  **`support-bot`**: Standalone support bot. Still uses its own SQLite file under `./db/`.
6.  **`dashboard`**: Admin dashboard backend + bundled frontend. **Ports**: `127.0.0.1:8080 → 8000`.

### Environment variables

Copy `.env.example` to `.env` and fill in:

```dotenv
POSTGRES_USER=xray
POSTGRES_PASSWORD=...       # required, compose refuses to start if empty
POSTGRES_DB=xray_vpn_bot
IMAGE_TAG=staging
```

`DATABASE_URL` is composed automatically inside compose:
`postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}`

### Initial Setup

```bash
# Create the external network (if required by your setup)
docker network create backend-network

# Postgres data volume — first start creates the DB
mkdir -p pg_data

# Support-bot still uses SQLite
mkdir -p db
touch db/db.sqlite3
```

### Launching

Startup order is enforced by `depends_on`: `postgres` (healthy) → `migrate` (completed) → `seller-bot` / `miniapp` / `dashboard`.

```bash
docker compose up -d --build
```

For an existing SQLite deployment, follow `docs/postgres-migration-runbook.md` to copy data into Postgres on first cutover.

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
