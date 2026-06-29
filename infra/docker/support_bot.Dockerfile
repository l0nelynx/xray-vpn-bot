FROM python:3.13-alpine

WORKDIR /usr/src/app

COPY services/support_bot/requirements_support.txt ./
RUN pip install --no-cache-dir -r requirements_support.txt
RUN apk add --no-cache bash procps

# COPY ./config.yml ./config.yml
COPY services/support_bot/support.py ./support.py
COPY services/support_bot/support_db.py ./support_db.py
# COPY ./db/db.sqlite3 ./db/db.sqlite3

CMD ["/bin/sh", "-c", "python support.py"]
