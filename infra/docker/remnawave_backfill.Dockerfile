# One-off maintenance image for the Remnawave 2.8 UUID -> numeric ID backfill.
# It deliberately runs only the standalone raw-HTTP script; no application
# service or Remnawave SDK code is started.
ARG BASE_IMAGE=ghcr.io/l0nelynx/python-base:staging
FROM ${BASE_IMAGE}

WORKDIR /app

# Use the schema/repositories from the same checkout as the script even when
# the locally cached production base image predates the rw_id migration.
COPY packages/common_db /tmp/common_db
RUN pip install --no-cache-dir --no-deps /tmp/common_db && rm -rf /tmp/common_db

COPY scripts/backfill_remnawave_ids.py ./backfill_remnawave_ids.py

RUN adduser -D -u 10001 appuser
USER appuser

ENTRYPOINT ["python", "/app/backfill_remnawave_ids.py"]
