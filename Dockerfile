FROM python:3.13-slim AS builder

WORKDIR /usr/src/build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ python3-dev patchelf \
    && rm -rf /var/lib/apt/lists/* \

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt nuitka
COPY ./app ./app
COPY ./uvicorn ./uvicorn
COPY ./main.py ./main.py
COPY ./support.py ./support.py
RUN python -m nuitka \
    --standalone \
    --include-package=uvicorn \
    --include-package=fastapi \
    --output-dir=dist \
    main.py

FROM debian:bookworm-slim

WORKDIR /usr/src/app

# Копируем результат компиляции (всю папку .dist)
COPY --from=builder /usr/src/build/dist/main.dist ./dist
RUN touch ./db.sqlite3

# Указываем путь к исполняемому файлу
CMD ["./dist/main.bin"]