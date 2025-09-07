FROM python

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN touch ./db.sqlite3

COPY ./app ./app
COPY ./uvicorn ./uvicorn
COPY ./main.py ./main.py
COPY ./support.py ./support.py

CMD ["/bin/bash", "-c", "python main.py"]
