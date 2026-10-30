# Shared Python base image for the three heavy backends (bot, dashboard, miniapp).
# Build context is the repository root.
# Use:  docker build -f infra/docker/base.Dockerfile -t ghcr.io/l0nelynx/python-base:staging .
#
# Carries the common third-party deps + the cross-service local packages, so the
# heavy compiled libraries (pydantic-core, sqlalchemy, asyncpg, psycopg2) are
# built and stored ONCE and shared by every service image that FROMs this.
# Service images add only their own extra deps + code on top.

FROM python:3.13.18-alpine3.24@sha256:7984cf56ceaddebe4fefeb75d64000b9f45d8b77b11a09b24524da6cdc3af0c8

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_CONSTRAINT=/opt/requirements-constraints.txt \
    PIP_NO_CACHE_DIR=1

# Runtime libs needed by all backends (curl for healthchecks, libpq for psycopg2).
RUN apk upgrade --no-cache && apk add --no-cache curl libpq

# Common third-party deps — single source of truth for these versions.
COPY infra/docker/requirements-base.txt /tmp/requirements-base.txt
COPY infra/docker/constraints.txt /opt/requirements-constraints.txt
RUN apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev \
 && pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r /tmp/requirements-base.txt \
 && apk del .build-deps \
 && rm -f /tmp/requirements-base.txt

# Cross-service local packages used by all three backends.
COPY packages/common_db /tmp/common_db
RUN pip install --no-cache-dir --no-build-isolation /tmp/common_db && rm -rf /tmp/common_db

COPY packages/remnawave_client /tmp/remnawave_client
RUN pip install --no-cache-dir --no-build-isolation /tmp/remnawave_client \
 && rm -rf /tmp/remnawave_client \
 && pip check
