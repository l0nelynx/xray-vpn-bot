# Build context for this Dockerfile is the repository root.
# Use:  docker build -f dashboard/Dockerfile .

# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY dashboard/frontend/package.json dashboard/frontend/package-lock.json* ./
RUN npm ci --ignore-scripts || npm install
COPY dashboard/frontend/ .
RUN npm run build

# Stage 2: Python runtime
FROM python:3.13-alpine
WORKDIR /app

RUN apk add --no-cache curl libpq

COPY dashboard/backend/requirements.txt .
RUN apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev \
 && pip install --no-cache-dir -r requirements.txt \
 && apk del .build-deps

COPY packages/remnawave_client /tmp/remnawave_client
RUN pip install --no-cache-dir /tmp/remnawave_client && rm -rf /tmp/remnawave_client

COPY dashboard/backend/ ./backend/
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY migrations_runner.py ./migrations_runner.py
COPY --from=frontend-build /build/dist ./static/

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
