FROM python:3.13.18-alpine3.24@sha256:7984cf56ceaddebe4fefeb75d64000b9f45d8b77b11a09b24524da6cdc3af0c8

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_CONSTRAINT=/opt/requirements-constraints.txt \
    PIP_NO_CACHE_DIR=1

WORKDIR /usr/src/app

COPY services/support_bot/requirements_support.txt ./
COPY infra/docker/constraints.txt /opt/requirements-constraints.txt
RUN apk upgrade --no-cache \
 && apk add --no-cache bash procps \
 && pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements_support.txt \
 && pip check

# COPY ./config.yml ./config.yml
COPY services/support_bot/support.py ./support.py
COPY services/support_bot/support_db.py ./support_db.py
# COPY ./db/db.sqlite3 ./db/db.sqlite3

RUN adduser -D -u 10001 appuser \
 && mkdir -p db \
 && chown -R appuser:appuser /usr/src/app
USER appuser

CMD ["python", "support.py"]
