# Build context is the repository root.
# Use:  docker build -f infra/docker/dashboard.Dockerfile .
# Requires the shared base image (infra/docker/base.Dockerfile) — pass a
# matching tag via --build-arg BASE_IMAGE=... (defaults to :staging).
#
# Pure JSON API. The SPA is built and served by the `frontend` container.
ARG BASE_IMAGE=ghcr.io/l0nelynx/python-base:staging
FROM ${BASE_IMAGE}

WORKDIR /app

# Dashboard-specific deps on top of the shared base.
COPY services/dashboard/backend/requirements.txt .
RUN apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev \
 && pip install --no-cache-dir -r requirements.txt \
 && apk del .build-deps

# Tariff Constructor provider metadata comes from the shared payments registry.
# Install with dependencies: unlike bot/miniapp, the dashboard requirements do
# not otherwise include aiohttp/aiosend.
COPY packages/payments /tmp/payments
RUN pip install --no-cache-dir /tmp/payments && rm -rf /tmp/payments

# Shared with miniapp: same image-validation/save logic for support-ticket
# attachments, so the two services can't drift on validation rules.
COPY packages/support_attachments /tmp/support_attachments
RUN pip install --no-cache-dir --no-deps /tmp/support_attachments && rm -rf /tmp/support_attachments

COPY services/dashboard/backend/ ./backend/
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY migrations_runner.py ./migrations_runner.py

# Drop privileges: the API is stateless (writes only to Postgres over the
# network), so it never needs root. Everything above ran as root; runtime does not.
RUN adduser -D -u 10001 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
