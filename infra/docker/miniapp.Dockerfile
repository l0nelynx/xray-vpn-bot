# Build context for this Dockerfile is the repository root.
# Use:  docker build -f infra/docker/miniapp.Dockerfile .
#
# Pure JSON API (miniapp / web portal / android). The SPA is built and served
# by the `frontend` container (infra/docker/frontend.Dockerfile).

FROM python:3.13-alpine
WORKDIR /app

RUN apk add --no-cache curl libpq

COPY services/miniapp/backend/requirements.txt .
RUN apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev \
 && pip install --no-cache-dir -r requirements.txt \
 && apk del .build-deps

COPY packages/remnawave_client /tmp/remnawave_client
RUN pip install --no-cache-dir /tmp/remnawave_client && rm -rf /tmp/remnawave_client

# Shared DB layer (Base, models, URL helpers) — single source of truth
# across app, dashboard and miniapp. See packages/common_db.
COPY packages/common_db /tmp/common_db
RUN pip install --no-cache-dir /tmp/common_db && rm -rf /tmp/common_db

# Shared Android<->Telegram merge logic. Depends on common_db and
# remnawave_client (installed above), so --no-deps avoids PyPI resolution of
# those local-only packages. See packages/account_linking.
COPY packages/account_linking /tmp/account_linking
RUN pip install --no-cache-dir --no-deps /tmp/account_linking && rm -rf /tmp/account_linking

# Shared payment-gateway providers + webhook signature verification. Its deps
# (aiohttp, aiosend) are already in the backend requirements, so --no-deps is
# safe. See packages/payments.
COPY packages/payments /tmp/payments
RUN pip install --no-cache-dir --no-deps /tmp/payments && rm -rf /tmp/payments

# Shared Android paid-delivery (seller fiat webhooks + miniapp IAP). Deps
# (sqlalchemy, remnawave_client) already present, so --no-deps is safe.
# See packages/subscription_delivery.
COPY packages/subscription_delivery /tmp/subscription_delivery
RUN pip install --no-cache-dir --no-deps /tmp/subscription_delivery && rm -rf /tmp/subscription_delivery

COPY services/miniapp/backend/ ./backend/
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY migrations_runner.py ./migrations_runner.py

EXPOSE 8001

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
