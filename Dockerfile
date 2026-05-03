FROM python:3.13-alpine

WORKDIR /usr/src/app

RUN apk add --no-cache bash curl

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Shared package — installed before app code so Docker layer cache survives
# changes inside ./app while packages/ stays untouched.
COPY packages/remnawave_client /tmp/remnawave_client
RUN pip install --no-cache-dir /tmp/remnawave_client && rm -rf /tmp/remnawave_client

RUN touch ./db.sqlite3

COPY ./app ./app
COPY ./main.py ./main.py
COPY ./support.py ./support.py

CMD ["/bin/sh", "-c", "python main.py"]
