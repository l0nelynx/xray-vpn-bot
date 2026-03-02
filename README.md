# Telegram VPN Sales Bot

Advanced Telegram bot for selling VPN subscriptions powered by Marzban VPN with multi-payment gateway support.

## Features
- 🔐 Sell VPN subscriptions via Telegram
- 💳 Multiple payment gateways (CryptoBot, Crystal Pay, A-Pays, Digiseller, Platega)
- 🌐 Integration with Marzban VPN API
- 💬 Dedicated support bot
- 📊 User database with SQLite
- 🚀 FastAPI webhook integration
- 🐳 Docker & Docker Compose support
- 🔄 Async/await architecture with aiogram 3.x
- 📱 Responsive keyboard UI optimization

## Quick Start

### Prerequisites
- Python 3.10+
- Docker & Docker Compose (optional)
- Marzban VPN instance
- Telegram Bot Token
- (Optional) Payment gateway credentials

### Configuration
1. Copy the example config file:
```bash
cp config-example.yml config.yml
```

2. Edit `config.yml` with your sensitive data (see `config-example.yml` for all available options):
```yaml
# Essential Configuration
token: "yourbottoken"
support_token: "yoursupportbottoken"
admin_id: "id"
marz_url: "https://example.com:8000"
auth_name: "username"
auth_pass: "password"

# Pricing
stars_price: 150              # Base price in TG Stars (1-month)
crypto_price: 2               # Base price in USDT (1-month)
sbp_price: 150                # Base price in RUB (1-month)
discount: 5                   # Discount % for 3+ month plans

# Free Plan Settings
free_traffic: 5               # Traffic limit in GB
free_days: 30                 # Duration in days

# Payment Gateways
crypto_bot_token: "token"
crystal_login: "login"
crystal_secret: "secret"
# ... additional payment gateway configs
```

3. **IMPORTANT SECURITY**: Add `config.yml` to `.gitignore` to prevent exposing sensitive data!

4. Create database:
```bash
mkdir -p db
touch db/db.sqlite3
```

### Run with Docker (VPN bot only)
```bash
docker build -t xray-vpn-bot .
docker run -d --name vpn-bot -v $(pwd)/config.yml:/app/config.yml xray-vpn-bot
```

### Run with Docker Compose (VPN + Support bot)
```bash
docker compose build
docker compose up -d
```

### Run Locally
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
python main.py &
python support.py &
wait
```

### Environment Setup (Local Development)
```bash
python -m venv venv
source venv/bin/activate  # or 'venv\Scripts\activate' on Windows
pip install -r requirements.txt
```

## Configuration Options

### Essential Settings
| Parameter | Type | Description |
|-----------|------|-------------|
| `token` | string | Telegram bot token |
| `support_token` | string | Support bot token |
| `admin_id` | integer | Admin Telegram ID |
| `marz_url` | string | Marzban API/Dashboard URL |
| `auth_name` | string | Marzban API username |
| `auth_pass` | string | Marzban API password |

### Pricing & Plans
| Parameter | Type | Description |
|-----------|------|-------------|
| `stars_price` | integer | 1-month plan price in TG Stars |
| `crypto_price` | float | 1-month plan price in USDT |
| `sbp_price` | integer | 1-month plan price in RUB (SBP) |
| `discount` | integer | Discount % for 3+ month plans |
| `free_traffic` | integer | Free plan traffic limit (GB) |
| `free_days` | integer | Free plan duration (days) |

### Payment Gateways
| Parameter | Description |
|-----------|-------------|
| `crypto_bot_token` | CryptoBot API token |
| `crystal_login` | Crystal Pay login |
| `crystal_secret` | Crystal Pay secret key |
| `crystal_salt` | Crystal Pay salt |
| `crystal_webhook` | Crystal Pay webhook URL |
| `apay_id` | A-Pays merchant ID |
| `apay_secret` | A-Pays secret key |
| `platega_api_key` | Platega API key |
| `platega_merchant_id` | Platega merchant ID |
| `dig_item_id_0` | Digiseller item ID |

### Server & Webhooks
| Parameter | Type | Description |
|-----------|------|-------------|
| `uvicorn_host` | string | Server host (default: 0.0.0.0) |
| `uvicorn_port` | integer | Server port (default: 5000) |
| `uvicorn_ssl_key` | string | Path to SSL private key |
| `uvicorn_ssl_cert` | string | Path to SSL certificate |
| `crystal_webhook_host` | string | Crystal Pay webhook URL |
| `webhook_host` | string | Payment webhook URL |

### URLs & References
| Parameter | Description |
|-----------|-------------|
| `agreement_url` | User agreement URL |
| `policy_url` | Privacy policy URL |
| `bot_url` | Telegram bot link |
| `news_url` | Telegram channel for news |
| `support_bot_id` | Support bot mention (@username) |

### Localization
| Parameter | Values | Description |
|-----------|--------|-------------|
| `language` | `ru` | Bot language (currently Russian only) |

## Project Structure
```
.
├── app/                          # Application code
│   ├── api/                      # Payment gateway integrations
│   │   ├── a_pay.py
│   │   ├── crystal_pay.py
│   │   ├── digiseller.py
│   │   ├── ggsel.py
│   │   └── remnawave/
│   ├── database/                 # Database models & queries
│   │   ├── models.py
│   │   └── requests.py
│   ├── handlers/                 # Bot command & event handlers
│   │   ├── base.py
│   │   ├── payments.py
│   │   ├── broadcast.py
│   │   └── events.py
│   ├── keyboards/                # UI buttons & keyboards
│   │   ├── keyboards.py
│   │   └── buttons.py
│   ├── locale/                   # Language files
│   │   └── lang_ru.py
│   ├── marzban/                  # Marzban VPN API
│   │   ├── marzban.py
│   │   └── templates.py
│   ├── support/                  # Support bot database
│   │   └── db.py
│   ├── settings.py               # Configuration loader
│   ├── utils.py                  # Utility functions
│   └── views.py                  # View helpers
├── db/                           # Database storage
│   └── db.sqlite3
├── uvicorn/                      # SSL certificates
│   └── ssl/
├── config-example.yml            # Example configuration
├── config.yml                    # Sensitive configuration (gitignored)
├── Dockerfile                    # Docker image definition
├── docker-compose.yml            # Docker Compose orchestration
├── main.py                       # VPN bot entry point
├── support.py                    # Support bot entry point
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Dependencies

Core Framework:
- **aiogram** 3.21+ - Modern async Telegram bot framework
- **FastAPI** 0.116+ - Web framework for webhooks
- **SQLAlchemy** 2.0+ - ORM for database operations

HTTP & Data:
- **aiohttp** 3.13+ - Async HTTP client
- **requests** 2.32+ - Synchronous HTTP client
- **aiosend** 3.0+ - CryptoBot API wrapper

Database:
- **aiosqlite** 0.21+ - Async SQLite driver

Configuration & Utils:
- **PyYAML** 6.0+ - YAML configuration parsing
- **python-dotenv** 1.1+ - Environment variable loading
- **pydantic** 2.11+ - Data validation
- **magic-filter** 1.0+ - Advanced filtering for handlers
- **orjson** 3.11+ - Fast JSON serialization

VPN Integration:
- **remnawave** 2.1+ - Marzban VPN API wrapper

## Troubleshooting

### Common Issues

**Bot token not recognized:**
```
AttributeError: Bot token not found
```
Ensure `token` is set in `config.yml`

**Database connection error:**
```
FileNotFoundError: config file not found
```
Run: `mkdir -p db && touch db/db.sqlite3`

**Webhook not receiving payments:**
- Verify `webhook_host`, `crystal_webhook_host` match your domain
- Check SSL certificates are valid
- Ensure firewall allows port 5000 (or configured port)

**Marzban connection failed:**
- Verify `marz_url` includes protocol (https://)
- Check `auth_name` and `auth_pass` credentials
- Ensure Marzban API is accessible from bot server

## Development

### Running Tests
```bash
python test.py
python test_keyboards.py
```

### Building Docker Image
```bash
docker build -t xray-vpn-bot:latest .
```

### Database Migrations
See `MIGRATION_GUIDE.md` for schema changes

### Performance Optimization
See `OPTIMIZATION_DETAILED.md` for keyboard and handler optimization tips

## License
MIT License - see [LICENSE](LICENSE) for details

## Support
For issues and feature requests, please open an issue on GitHub.

---
**Made with ❤️ for the VPN community**
