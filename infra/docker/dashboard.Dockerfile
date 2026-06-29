# Build context for this Dockerfile is the repository root.
# Use:  docker build -f infra/docker/dashboard.Dockerfile .

# Stage 1: Build React frontend (npm workspaces — needs the root manifest and
# the shared web/packages alongside this app).
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY package.json package-lock.json* ./
COPY web/packages ./web/packages
# Both workspace frontends are listed in the root manifest, so their package
# manifests must be present for the workspace install to resolve. Only the
# target app is built.
COPY web/apps/dashboard/package.json ./web/apps/dashboard/package.json
COPY web/apps/miniapp/package.json ./web/apps/miniapp/package.json
RUN npm ci || npm install
COPY web/apps/dashboard ./web/apps/dashboard
RUN npm run build -w xray-vpn-dashboard

# Stage 2: Python runtime
FROM python:3.13-alpine
WORKDIR /app

RUN apk add --no-cache curl libpq

COPY services/dashboard/backend/requirements.txt .
RUN apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev \
 && pip install --no-cache-dir -r requirements.txt \
 && apk del .build-deps

COPY packages/remnawave_client /tmp/remnawave_client
RUN pip install --no-cache-dir /tmp/remnawave_client && rm -rf /tmp/remnawave_client

# Shared DB layer (Base, models, URL helpers) — single source of truth
# across app, dashboard and miniapp. See packages/common_db.
COPY packages/common_db /tmp/common_db
RUN pip install --no-cache-dir /tmp/common_db && rm -rf /tmp/common_db

COPY services/dashboard/backend/ ./backend/
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY migrations_runner.py ./migrations_runner.py
COPY --from=frontend-build /build/web/apps/dashboard/dist ./static/

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
