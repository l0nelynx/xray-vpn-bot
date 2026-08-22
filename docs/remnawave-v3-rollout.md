# Remnawave v3 rollout

Use this runbook only after the 2.8 ID backfill reports `ready: true`. The v3
application release uses `remnawave-api==3.0.1` and numeric Remnawave user IDs
throughout delivery, CRM, account linking, webhooks and HWID operations.

`users.vless_uuid` is the historical Remnawave panel-user UUID despite its old
name. It remains read-only audit/rollback data and is not used for lookup,
ownership, mutation or account merge decisions.

## 1. Back up and record the release

Back up all of the following before changing either side:

- application PostgreSQL database;
- Remnawave database;
- Remnawave `.env` and panel configuration;
- application `.env` and `config.yml`;
- the currently deployed Stage 1 image tag and panel 2.8 version.

Do not use a floating image tag for the maintenance window. Record the exact
Stage 2 `sha-*` or numbered staging tag that will be deployed.

## 2. Stop consumers

Keep PostgreSQL and Redis running, but stop every process that can deliver,
provision, merge or mutate a Remnawave user:

```bash
docker compose stop bot miniapp dashboard crm-worker
```

The frontend may stay up in maintenance mode, but it must not be able to reach
a running MiniApp or Dashboard backend.

## 3. Upgrade Remnawave

Follow the Remnawave v3 upgrade instructions and rename the panel secret:

```dotenv
APP_SECRET=<the previous JWT_AUTH_SECRET value>
```

Remove `JWT_AUTH_SECRET` only as directed by the panel upgrade procedure. Do
not generate a different `APP_SECRET` during this migration unless the panel
documentation explicitly requires rotation.

Confirm that the panel is healthy and its API token is still valid before
starting application workers.

## 4. Deploy fresh Stage 2 images

Pull/build the shared base from scratch. This prevents the archived
`remnawave` distribution and `remnawave-api` from coexisting in an old layer:

```bash
docker compose pull base bot dashboard miniapp
docker compose up migrate
```

Migration `0036_crm_delivery_rw_id` adds `crm_campaign_deliveries.rw_id` and
backfills historical rows only when one local user matches unambiguously.

Verify the installed distributions in the new image:

```bash
docker compose run --rm --no-deps bot python -c \
  "import importlib.metadata as m; print(m.version('remnawave-api')); print(m.packages_distributions().get('remnawave'))"
```

Expected package version: `3.0.1`. The import package maps only to
`remnawave-api`; a separate distribution named `remnawave` must not be
installed.

## 5. Smoke test before starting workers

Run a read/HWID test against a known numeric Remnawave user ID:

```bash
docker compose run --rm --no-deps bot \
  python scripts/smoke_remnawave_v3.py --rw-id 1184
```

Then run the opt-in mutation test. It creates a uniquely marked disposable
profile, updates it, resets traffic, lists HWID devices and deletes the profile
in `finally`:

```bash
docker compose run --rm --no-deps bot \
  python scripts/smoke_remnawave_v3.py --mutating
```

Both commands must return JSON with `"ok": true`. If cleanup reports an ID,
delete only that `stage2-smoke:*` profile manually before proceeding. Test an
actual HWID device deletion separately only on a disposable client/device.

## 6. Start services and verify flows

```bash
docker compose up -d bot dashboard miniapp crm-worker
docker compose ps
docker compose logs migrate bot dashboard miniapp crm-worker --tail 100
```

Verify in this order:

1. existing subscription read and device list by `rw_id`;
2. MiniApp FREE creation;
3. paid delivery to an existing subscription;
4. paid delivery that creates a new subscription;
5. account linking by shortUuid and a multi-subscription merge;
6. CRM preview and a one-user perk campaign;
7. v3 user and torrent-blocker webhook resolution by numeric ID;
8. retry of any transaction that remained `pending` during maintenance.

An API timeout must fail/pause the operation. It must never be interpreted as
`not found` and must not trigger creation of another Remnawave profile.

## Rollback

Rollback is coordinated, never application-only:

1. stop bot, MiniApp, Dashboard and CRM worker;
2. restore the Remnawave 2.8 database/configuration backup;
3. restore the application database backup if Stage 2 writes occurred;
4. deploy the recorded Stage 1 application images;
5. start services only after panel 2.8 health checks pass.

Do not run the Stage 1 application against panel v3, or the Stage 2 application
against panel 2.8.
