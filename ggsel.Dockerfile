FROM python:3.13-alpine

WORKDIR /usr/src/app

COPY ggsel_requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN touch ./db.sqlite3
RUN apk add --no-cache bash

COPY ./app ./app
COPY ./backend.py ./backend.py

CMD ["/bin/sh", "-c", "python backend.py"]
