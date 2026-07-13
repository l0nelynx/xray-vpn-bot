# Build context is the repository root.
# Use:  docker build -f infra/docker/bot.Dockerfile .
# Requires the shared base image (infra/docker/base.Dockerfile) — pass a
# matching tag via --build-arg BASE_IMAGE=... (defaults to :staging).
ARG BASE_IMAGE=ghcr.io/l0nelynx/python-base:staging
FROM ${BASE_IMAGE}

WORKDIR /usr/src/app

RUN apk add --no-cache bash postgresql-client

# Bot-specific deps on top of the shared base.
COPY services/bot/requirements.txt ./
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

RUN touch ./db.sqlite3

COPY services/bot/app ./app
COPY services/bot/main.py ./main.py
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY migrations_runner.py ./migrations_runner.py
COPY services/bot/scripts ./scripts

CMD ["/bin/sh", "-c", "python main.py"]
