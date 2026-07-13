# Shared Python base image for the three heavy backends (bot, dashboard, miniapp).
# Build context is the repository root.
# Use:  docker build -f infra/docker/base.Dockerfile -t ghcr.io/l0nelynx/python-base:staging .
#
# Carries the common third-party deps + the cross-service local packages, so the
# heavy compiled libraries (pydantic-core, sqlalchemy, asyncpg, psycopg2) are
# built and stored ONCE and shared by every service image that FROMs this.
# Service images add only their own extra deps + code on top.

FROM python:3.13-alpine

# Runtime libs needed by all backends (curl for healthchecks, libpq for psycopg2).
RUN apk add --no-cache curl libpq

# Common third-party deps — single source of truth for these versions.
COPY infra/docker/requirements-base.txt /tmp/requirements-base.txt
RUN apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev \
 && pip install --no-cache-dir -r /tmp/requirements-base.txt \
 && apk del .build-deps \
 && rm -f /tmp/requirements-base.txt

# Cross-service local packages used by all three backends.
COPY packages/common_db /tmp/common_db
RUN pip install --no-cache-dir /tmp/common_db && rm -rf /tmp/common_db

COPY packages/remnawave_client /tmp/remnawave_client
RUN pip install --no-cache-dir /tmp/remnawave_client && rm -rf /tmp/remnawave_client
