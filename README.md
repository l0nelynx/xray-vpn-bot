# Telegram VPN Sales Bot

Simple Telegram bot for selling VPN subscriptions powered by Marzban VPN.

## Features
- Sell VPN subscriptions via Telegram
- Integration with Marzban VPN API
- Support Bot

## Quick Start

### Prerequisites
- Python 3.10+
- Docker (optional)

### Configuration
1. Copy the example config file:
```bash
cp config-example.yml config.yml
```
2. Edit config.yml with your sensitive data (see ``config-example.yml``):
```yaml
token: "yourbottoken"
admin_id: "id" # Admin Telegram ID
marz_url: "https://example.com:8000" # Marzban API/Dashboard address
auth_name: "John" # Marzban API login
auth_pass: "Internet" # Marzban API password
crypto_bot_token: "JohnBitcoin" # API token for CryptoBot
stars_price: 150 # Base price of 1-month plan in TG_Stars
crypto_price: 2 # Base price of 1-month plan in USDT
free_traffic: 5 # Traffic limit in Gb for FREE plan
free_days: 30 # Plan limit in Days for FREE plan
```
3. IMPORTANT SECURITY: Add config.yml to .gitignore to prevent exposing sensitive data!

### Run with Docker (only VPN bot)
```bash
make build  # Build Docker image
make run    # Start container
```
### Run with Docker Compose (bot VPN and support bots)
```bash
docker compose build  # Build Docker images
docker compose up -d    # Start containers
```
### Run locally
```bash
pip install -r requirements.txt
python main.py & python support.py $ wait
```
### Makefile Commands
| **command** | **description**               |
|-------------|-------------------------------|
| ``build``   | Build Docker image            |
| ``run``     | Start container in background |
| ``stop``    | Stop running container        |
| ``dell``    | Remove container              |
| ``run_it``    | Start container with interactive mode option             |
### Environment Setup
Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
Project Structure
```text
├── app/                  # app code
├── .gitignore
├── config-example.yml    # Example configuration
├── config.yml            # Sensitive data
├── db.sqlite3            # db
├── Dockerfile
├── Makefile
├── main.py
├── README.md
└── requirements.txt
```
## License
MIT License - see [LICENSE](https://github.com/l0nelynx/xray-vpn-bot/blob/main/LICENSE) for details
