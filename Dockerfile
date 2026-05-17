FROM python:3.13-alpine

WORKDIR /usr/src/app

RUN apk add --no-cache bash curl postgresql-client libpq

COPY requirements.txt ./
RUN apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev \
 && pip install --no-cache-dir -r requirements.txt \
 && apk del .build-deps

# Shared package — installed before app code so Docker layer cache survives
# changes inside ./app while packages/ stays untouched.
COPY packages/remnawave_client /tmp/remnawave_client
RUN pip install --no-cache-dir /tmp/remnawave_client && rm -rf /tmp/remnawave_client

# Shared DB layer (Base, models, URL helpers) — single source of truth
# across app, dashboard and miniapp. See packages/common_db.
COPY packages/common_db /tmp/common_db
RUN pip install --no-cache-dir /tmp/common_db && rm -rf /tmp/common_db

RUN touch ./db.sqlite3

COPY ./app ./app
COPY ./main.py ./main.py
COPY ./support.py ./support.py
COPY ./alembic ./alembic
COPY ./alembic.ini ./alembic.ini
COPY ./migrations_runner.py ./migrations_runner.py
COPY ./scripts ./scripts

CMD ["/bin/sh", "-c", "python main.py"]
