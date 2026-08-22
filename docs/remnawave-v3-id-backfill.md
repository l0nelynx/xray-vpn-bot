# Remnawave 2.8 → 3.0: numeric ID backfill

Run this procedure **before** upgrading the Remnawave panel. Version 2.8 is
the last point where the panel response contains the legacy user `uuid`, the
protocol `vlessUuid`, and the numeric user `id` together.

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
docker compose --profile maintenance run --rm --no-deps rw-id-backfill \
  --repair-primary 2001:1184
```

`--repair-primary USER_ID:RW_ID` is an explicit operator confirmation that the
given `user_subscriptions` primary is authoritative. The script validates that
the primary has not changed, then plans synchronization of the denormalized
`users.rw_id` field. Other primary mismatches remain blockers.

Review the JSON report:

- `blocker_counts` must contain only zeroes;
- `planned.resolve_legacy` is the number of `users.rw_id` values to recover;
- `planned.resolve_protocol_vless` is the number recovered from protocol
  `vlessUuid` values accidentally persisted by the old Android claim/migrate
  implementation;
- `planned.resolve_email` is the number whose stale UUID was absent from the
  panel but whose local email matched exactly one current Remnawave profile;
- `panel_users_with_protocol_vless_uuid` should equal `panel_users`; if the
  endpoint returns no protocol UUIDs at all, the script stops with exit code 3
  instead of producing an incomplete audit;
- `planned.attach_existing` is the number of missing
  `user_subscriptions` rows to create;
- `ignored_counts.non_uuid_legacy_values` contains historical sentinel or
  malformed values (for example the literal string `None`); they are reported
  for audit but are not panel identities and therefore do not block migration;
- `ignored_counts.missing_panel_profiles_without_active_paid_transaction`
  contains users whose valid stored UUID no longer exists in Remnawave, whose
  email did not resolve to exactly one current profile, and who have no active
  paid transaction; the script treats these as deleted expired profiles,
  preserves the local UUID for audit, and does not block migration;
- `unresolved_active_paid_details` contains transaction ID, status, expiry,
  delivery status and target `rw_id` when a missing panel profile still has an
  active `confirmed` or `delivered` transaction; these users remain blockers;
- duplicate UUIDs, a UUID shared by different panel/protocol identities, and
  local ownership conflicts are blockers; no changes are applied in this case;
- if a local email matches multiple current Remnawave profiles,
  `ambiguous_email_matches` blocks all writes and lists their numeric IDs;
- `primary_mismatch_details` shows both `users.rw_id` and the primary
  subscription `rw_id` for every projection mismatch;
- `ready` is expected to be `false` while safe changes are still planned.

Exit code `2` means blockers were found and no write is permitted. Resolve the
listed local user IDs manually and repeat the dry-run. Exit code `3` means a
configuration, database, or Remnawave API failure.

## 4. Apply in a short maintenance window

Stop services that can create or merge users, but keep Postgres running:

```bash
docker compose stop bot miniapp dashboard crm-worker
docker compose --profile maintenance run --rm --no-deps rw-id-backfill \
  --repair-primary 2001:1184 --apply
```

The apply command re-runs the ownership audit inside its database transaction.
It then:

1. maps `users.vless_uuid` to numeric `rw_id`, accepting either the intended
   legacy panel-user `uuid` or the protocol `vlessUuid` written by the old
   Android bug;
2. if neither UUID exists on the current panel, tries one exact normalized
   email match;
3. creates missing `user_subscriptions` ownership rows;
4. preserves an already-established primary subscription;
5. otherwise makes the recovered profile primary;
6. rolls back the whole transaction on any conflict.

## 5. Verify

Run the dry-run once more:

```bash
docker compose --profile maintenance run --rm --no-deps rw-id-backfill \
  --repair-primary 2001:1184
```

The final report must contain:

```json
{
  "ready": true,
  "planned": {
    "attach_existing": 0,
    "resolve_email": 0,
    "resolve_legacy": 0,
    "resolve_protocol_vless": 0
  }
}
```

Only after that result is it safe to upgrade Remnawave to v3 and deploy the
application release using `remnawave-api==3.0.1`.
