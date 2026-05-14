# Runbook: SQLite → PostgreSQL миграция

## Предусловия
- Все ветки кода из плана `2026-05-13-postgres-extraction` влиты в `main`.
- Образ `seller-bot:postgres` собран и пушнут.
- На хосте есть свободные ~2 ГБ под `./pg_data/`.
- В `.env` заполнены `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`.

## Шаги

1. **Анонсируем downtime в Telegram-канале** (~15 мин окно).

2. **Стопаем все сервисы (бот, miniapp, dashboard, support-bot):**
   ```bash
   docker compose stop seller-bot miniapp dashboard support-bot
   ```

3. **Делаем снапшот SQLite:**
   ```bash
   cp db/db.sqlite3 db/db.sqlite3.snapshot-$(date +%F-%H%M)
   ```
   (этот файл — точка отката)

4. **Поднимаем postgres и ждём healthy:**
   ```bash
   docker compose up -d postgres
   docker compose ps  # postgres -> healthy
   ```

5. **Накатываем схему:**
   ```bash
   docker compose run --rm migrate
   ```

6. **Переносим данные:**
   ```bash
   docker compose run --rm \
     -v $(pwd)/db:/data \
     -e SQLITE_PATH=/data/db.sqlite3.snapshot-YYYY-MM-DD-HHMM \
     -e DATABASE_URL='postgresql+psycopg2://xray:${POSTGRES_PASSWORD}@postgres:5432/xray_vpn_bot' \
     migrate python scripts/sqlite_to_postgres.py
   ```

7. **Поднимаем сервисы:**
   ```bash
   docker compose up -d seller-bot miniapp dashboard
   ```

8. **Smoke-тесты:**
   - `curl -f http://127.0.0.1:5000/health`
   - `curl -f http://127.0.0.1:8080/health`
   - Открыть бот в Telegram, выполнить `/start` — данные на месте.
   - Открыть miniapp — список устройств / подписка отображаются.
   - В dashboard открыть список пользователей — миграция перенесла строки.

9. **Если ОК — снимаем downtime-анонс. Снапшот SQLite держим минимум 7 дней.**

## Откат

Если после шага 7 что-то пошло не так:
```bash
docker compose stop seller-bot miniapp dashboard
# В compose поменять DATABASE_URL обратно на DB_PATH=/usr/src/app/db/db.sqlite3
# (для отката лучше держать тег коммита «до перевода» в git).
docker compose up -d seller-bot miniapp dashboard
```
SQLite-снапшот лежит в `db/db.sqlite3.snapshot-...` — копируется обратно в `db/db.sqlite3` при необходимости.

## Регулярные бэкапы после миграции

- `app/admin/backup.py` сам определяет, какой бэкенд активен (`DATABASE_URL` начинается на `postgresql` → `pg_dump`, иначе — копия SQLite).
- На bot-контейнере уже стоит `postgresql-client`, так что `pg_dump` доступен без донастройки.
- Архив отдаётся через Telegram, как и раньше; внутри — `db.sql` для Postgres-варианта.
