FROM python:3.13.18-alpine3.24@sha256:7984cf56ceaddebe4fefeb75d64000b9f45d8b77b11a09b24524da6cdc3af0c8
COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_CONSTRAINT=/opt/requirements-constraints.txt \
    UV_NO_CACHE=1

WORKDIR /usr/src/app

COPY services/support_bot/requirements_support.txt ./
COPY infra/docker/constraints.txt /opt/requirements-constraints.txt
RUN apk upgrade --no-cache \
 && apk add --no-cache bash procps \
 && uv pip uninstall --system pip \
 && rm -rf /usr/local/lib/python3.13/ensurepip \
 && uv pip install --system setuptools wheel \
 && uv pip install --system -r requirements_support.txt \
 && uv pip check --system

# COPY ./config.yml ./config.yml
COPY services/support_bot/support.py ./support.py
COPY services/support_bot/support_db.py ./support_db.py
# COPY ./db/db.sqlite3 ./db/db.sqlite3

RUN adduser -D -u 10001 appuser \
 && mkdir -p db \
 && chown -R appuser:appuser /usr/src/app
USER appuser

CMD ["python", "support.py"]
