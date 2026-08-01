# Remnawave 2.8 → 3.0: numeric ID backfill

Run this procedure **before** upgrading the Remnawave panel. Version 2.8 is
the last point where the panel response contains both the legacy user `uuid`
and the numeric user `id`.

The maintenance script is SDK-independent, does not print the API token, and
uses dry-run mode unless `--apply` is supplied. Writes are atomic: any
unresolved UUID, ambiguous mapping, missing panel ID, primary mismatch, or
ownership conflict prevents all changes.

## 1. Back up production

Back up the application Postgres database, the Remnawave database, and both
configuration files. Keep the Remnawave panel on 2.8 during all steps below.

## 2. Build the isolated one-off runner

The maintenance profile has its own image and does not replace or start any
application service:

```bash
docker compose --profile maintenance build rw-id-backfill
```

It reuses the existing Python base image but installs the current `common_db`
models into the one-off image. Building it does not restart the bot, Dashboard,
MiniApp, workers, Postgres, or Remnawave.

## 3. Dry-run

```bash
docker compose --profile maintenance run --rm --no-deps rw-id-backfill
```

Review the JSON report:

- `blocker_counts` must contain only zeroes;
- `planned.resolve_legacy` is the number of `users.rw_id` values to recover;
- `planned.attach_existing` is the number of missing
  `user_subscriptions` rows to create;
- `ready` is expected to be `false` while safe changes are still planned.

Exit code `2` means blockers were found and no write is permitted. Resolve the
listed local user IDs manually and repeat the dry-run. Exit code `3` means a
configuration, database, or Remnawave API failure.

## 4. Apply in a short maintenance window

Stop services that can create or merge users, but keep Postgres running:

```bash
docker compose stop bot miniapp dashboard crm-worker
docker compose --profile maintenance run --rm --no-deps rw-id-backfill --apply
```

The apply command re-runs the ownership audit inside its database transaction.
It then:

1. maps `users.vless_uuid` (legacy panel user UUID) to numeric `rw_id`;
2. creates missing `user_subscriptions` ownership rows;
3. preserves an already-established primary subscription;
4. otherwise makes the recovered profile primary;
5. rolls back the whole transaction on any conflict.

## 5. Verify

Run the dry-run once more:

```bash
docker compose --profile maintenance run --rm --no-deps rw-id-backfill
```

The final report must contain:

```json
{
  "ready": true,
  "planned": {
    "attach_existing": 0,
    "resolve_legacy": 0
  }
}
```

Only after that result is it safe to upgrade Remnawave to v3 and deploy the
application release using `remnawave-api==3.0.1`.
