FROM python:3.13-alpine

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN touch ./db.sqlite3
RUN apk add --no-cache bash

COPY ./app ./app
COPY ./uvicorn ./uvicorn
COPY ./main.py ./main.py
COPY ./support.py ./support.py

CMD ["/bin/sh", "-c", "python main.py"]
