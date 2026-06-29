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

COPY services/dashboard/backend/ ./backend/
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY migrations_runner.py ./migrations_runner.py

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
