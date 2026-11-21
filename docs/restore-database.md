# Restore a database backup from Telegram

The bot sends the administrator a file named `backup_YYYYMMDD_HHMMSS.zip`, either on schedule or through the **Бекап БД** button. The production Docker Compose deployment puts a plain PostgreSQL dump called `db.sql` inside this ZIP. A bot running with SQLite puts `db.sqlite3` inside instead.

The archive covers the main application database. Supply the deployment's original `.env`, `config.yml`, support uploads and any separate support-bot database from their own copies. Keep the original `payments_secrets_key` (or `dashboard_secret` when used as its fallback) so the application can decrypt stored integration credentials.

## 1. Check the archive and target

On the destination Linux host, open Bash in the project directory. On a fresh host, prepare the Compose files, configuration, images and networks first. Leave the application stopped until the import is complete. [Deployment instructions](deployment.md)

```bash
cd /opt/xray-vpn-bot
archive=/path/to/backup_YYYYMMDD_HHMMSS.zip   # Set this to the actual file.
umask 077
work=$(mktemp -d)
unzip -t "$archive" && unzip -Z1 "$archive"
docker compose ls -a
docker compose ps -a
```

Continue only if the ZIP passes its integrity check. If the destination already runs this deployment, confirm that `docker compose ps -a` shows its existing `postgres` service. If it shows an empty project while `docker compose ls -a` lists the running stack, select the original Compose project and file list before continuing. Use the same shell and Compose settings throughout.

## 2. Import `db.sql` into a new PostgreSQL database

The commands below create a second database inside the project's `postgres` service. The existing application database stays available for rollback. Allow room for both databases and the extracted SQL file. Use the same application release that produced the backup or a release that includes its Alembic revision.

```bash
unzip -p "$archive" db.sql > "$work/db.sql" && test -s "$work/db.sql"
```

After extraction succeeds, start PostgreSQL and import the dump. The role comes from the container's `POSTGRES_USER`. The PostgreSQL client tools run inside that same container.

```bash
restore_db="xray_restore_$(date +%Y%m%d_%H%M%S)"
docker compose up -d --wait postgres &&
  docker compose exec -T postgres sh -ec 'exec createdb -U "$POSTGRES_USER" -T template0 "$1"' sh "$restore_db" &&
  docker compose exec -T postgres sh -ec 'exec psql -X -v ON_ERROR_STOP=1 --single-transaction -U "$POSTGRES_USER" -d "$1" -f -' sh "$restore_db" < "$work/db.sql"
```

If the import reports an error, stop here. The transaction rolls back on SQL errors. Check the first `psql` error before retrying. For an unrecognized setting or backslash command, compare the dump header's `Dumped by pg_dump version` with the destination server and client versions. [PostgreSQL dump and restore reference](https://www.postgresql.org/docs/16/backup-dump.html)

For example, a newer dump client can emit `SET transaction_timeout = 0;`, which PostgreSQL 16 rejects. If that is the reported error, keep the original ZIP, remove just that session setting from the header of the extracted SQL copy, and repeat the `psql` import into the still-empty recovery database. Keep `ON_ERROR_STOP` enabled so other compatibility errors remain visible.

Verify the restored database before changing the application configuration:

```bash
docker compose exec -T postgres sh -ec 'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1"' sh "$restore_db" <<'SQL'
SELECT current_database();
SELECT version_num FROM alembic_version;
SELECT count(*) AS users FROM users;
SELECT count(*) AS transactions FROM transactions;
SQL
```

Check the counts against what you expect at the time of the Telegram backup. Later payments, subscriptions and user changes will need reconciliation.

## 3. Switch the application to the verified database

1. Pause incoming traffic and other writers. Stop the application services that use PostgreSQL. Save the current configuration in the private recovery directory:

   ```bash
   docker compose stop bot dashboard miniapp crm-worker
   cp -p .env "$work/env.before-restore"
   printf 'Set this value in .env: POSTGRES_DB=%s\n' "$restore_db"
   ```

2. Edit the existing `POSTGRES_DB` entry in `.env`, or add it if absent, using the value printed above. Clear any shell override with `unset POSTGRES_DB`. Keep `POSTGRES_USER`, `POSTGRES_PASSWORD` and the `pg_data` mount as configured. With the supplied Compose file, this setting selects the database for migrations and all application services.

3. If you are rolling production back in time, review any pending CRM jobs in Redis before resuming the worker. Its queue may contain jobs created after the backup. Start the stack and check migration status:

   ```bash
   docker compose up -d
   docker compose ps -a
   docker compose logs --tail=50 migrate
   ```

   Expect `migrate` to exit with code 0. Check a known user and transaction in the dashboard before reopening traffic.

**Rollback.** While traffic is paused, stop the same four services, restore the previous `POSTGRES_DB` value (or restore `.env` from `"$work/env.before-restore"` if that was the only change), then run `docker compose up -d`. Writes made to the restored database after the switch stay in that database.

## SQLite archives containing `db.sqlite3`

For a deployment configured to use SQLite, extract the file into the private recovery directory and check it with the SQLite CLI:

```bash
unzip -p "$archive" db.sqlite3 > "$work/db.sqlite3" &&
  test -s "$work/db.sqlite3" &&
  sqlite3 -readonly "$work/db.sqlite3" 'PRAGMA integrity_check; SELECT count(*) FROM users;'
```

Expect `ok` and a plausible user count. Stop all processes using the application database. Copy the verified file to a **new filename** in the application's persistent data directory, grant the application user read/write access, and point `DB_PATH` to that file. If the deployment sets an explicit SQLite `DATABASE_URL`, update it to the same file. Restart the original services and check a known record. Keep the previous database and its WAL/SHM files together for rollback. The separate support bot uses its own SQLite file under `db/`.
