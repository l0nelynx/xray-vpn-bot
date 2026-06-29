# Build context is the repository root.
# Use:  docker build -f infra/docker/miniapp.Dockerfile .
# Requires the shared base image (infra/docker/base.Dockerfile) — pass a
# matching tag via --build-arg BASE_IMAGE=... (defaults to :staging).
#
# Pure JSON API (miniapp / web portal / android). The SPA is built and served
# by the `frontend` container.
ARG BASE_IMAGE=ghcr.io/l0nelynx/python-base:staging
FROM ${BASE_IMAGE}

WORKDIR /app

# MiniApp-specific deps on top of the shared base.
COPY services/miniapp/backend/requirements.txt .
RUN apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev \
 && pip install --no-cache-dir -r requirements.txt \
 && apk del .build-deps

# Shared local packages used by bot + miniapp (common_db + remnawave_client are
# already in the base image). --no-deps: their deps are present in base/extras.
COPY packages/account_linking /tmp/account_linking
RUN pip install --no-cache-dir --no-deps /tmp/account_linking && rm -rf /tmp/account_linking
COPY packages/payments /tmp/payments
RUN pip install --no-cache-dir --no-deps /tmp/payments && rm -rf /tmp/payments
COPY packages/subscription_delivery /tmp/subscription_delivery
RUN pip install --no-cache-dir --no-deps /tmp/subscription_delivery && rm -rf /tmp/subscription_delivery

COPY services/miniapp/backend/ ./backend/
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY migrations_runner.py ./migrations_runner.py

# Drop privileges: the API is stateless (writes only to Postgres over the
# network), so it never needs root. Everything above ran as root; runtime does not.
RUN adduser -D -u 10001 appuser
USER appuser

EXPOSE 8001

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
