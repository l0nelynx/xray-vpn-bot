FROM python

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN touch db.sqlite3

COPY . .

CMD ["/bin/bash", "-c", "python main.py"]