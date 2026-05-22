# Android subscription import by URL — design

**Date:** 2026-05-21
**Scope:** `app/handlers/android_link_merge.py` (new function), `miniapp/backend/android/link_router.py` (new endpoint), `miniapp/backend/android/schemas_data.py` (request/response schemas), `tests/conftest.py` (extend `FakeRemnawave`), `tests/test_android_link_merge.py` and `tests/test_link_by_url_router.py` (tests).

## Problem

User A is signed into the Android app (has their own `users` row). They obtained a Remnawave subscription URL belonging to user B — e.g. a subscription purchased in Telegram before the Android app existed — and want to take it over. Today there is no API for this; manual support intervention is required.

We add `POST /api/android/link/by_url` which accepts the subscription URL, looks up B in Remnawave by its `short_uuid`, applies the same PRO/FREE resolution matrix that `merge_android_and_tg` uses, and either rewrites `A.vless_uuid` (best-case merge) or refuses (both PRO). The B-side does NOT have to exist as a `users` row in our DB — Remnawave is the only source of truth for B.

## PRO/FREE classification

Same rule as the rest of the project: `status == "active" and data_limit is None` → PRO. 404/None → `"none"`. Re-uses the existing `_classify(info)` helper without modification.

## Resolution matrix

Reuses `_decide(...)`. We map `A → "android-side"` (current user) and `B → "tg-side"` (imported subscription) when calling `_decide`. The `survivor_id`/`loser_id` outputs are meaningless here (there is only one DB row), so we ignore them — only `chosen_uuid` and `result_code` matter.

| A (current user) | B (imported via URL) | result | `chosen_uuid` (becomes A.vless_uuid) | `loser_rw_uuid` (deactivated in RW) |
|---|---|---|---|---|
| pro | pro | `MergeBlocked` → `both_pro_support_needed` | — | — |
| pro | free | `merged_pro` | A.uuid | B.uuid |
| free | pro | `merged_pro` | B.uuid | A.uuid |
| free | free | `merged_free` | B.uuid | A.uuid |
| none | pro | `ok` | B.uuid | None |
| none | free | `ok` | B.uuid | None |

Rows "X + none" from the original matrix are unreachable: we only enter the function after a successful RW lookup of B by short_uuid. If B isn't found, we raise `LookupNotFound` before classification.

**Self-import short-circuit:** if `A.vless_uuid == B.uuid` (the user pasted their own URL), the function returns `{"result": "already_owned", ...}` without any DB or RW writes. A-side lookup is skipped because it would query the same RW row.

**Rationale for FREE+FREE → B wins:** in the original tg-link matrix, the "T-side" wins among two FREE accounts because TG represents the user's active identity. Here B-side is the imported subscription — the explicit object of the user's action — so the same "user-intent wins" logic applies.

## Architecture

### `app/handlers/android_link_merge.py` — additions

**New exception:**

```python
class LookupNotFound(Exception):
    """Raised when get_user_by_short_uuid_raw returns None — the URL
    pointed at a non-existent Remnawave user. Router maps to HTTP 404."""
```

**New internal helper `_lookup_a_and_b_in_rw`:** concurrent RW lookup of A (by `vless_uuid` → `email` fallback) and B (by `short_uuid`). Errors and 404 → None. Stylistically mirrors `_lookup_rw` but without the username fallback (we don't have B's username) and with `short_uuid` instead of plain `uuid`.

**New public coroutine:**

```python
async def import_subscription_by_uuid(
    session,
    *,
    current_user_id: int,
    b_rw_short_uuid: str,
) -> dict[str, Any]:
    """
    Returns:
      {
        "result": str,                  # merged_pro | merged_free | ok | already_owned
        "a_tier": str,                  # pro | free | none
        "b_tier": str,                  # pro | free  (B always exists in RW)
        "a_rw_uuid": str | None,
        "b_rw_uuid": str,               # always set
        "chosen_uuid": str,             # uuid written to A.vless_uuid
        "loser_rw_uuid": str | None,    # uuid to deactivate in RW (best-effort)
      }

    Raises:
      MergeBlocked    — both A and B are PRO. No DB writes, no RW writes.
      LookupNotFound  — Remnawave returned no user for the short_uuid.
    """
```

Caller commits the session.

### Internal flow inside `import_subscription_by_uuid`

1. `A = await session.get(User, current_user_id)`. If None → `RuntimeError("a_user_not_found")` (treat as 500 in router).
2. `b_info = await rem.get_user_by_short_uuid_raw(b_rw_short_uuid)`. If None → raise `LookupNotFound`.
3. **Self-import check:** if `A.vless_uuid` is not None and `A.vless_uuid == b_info["uuid"]` → return `{"result": "already_owned", "a_tier": _classify(b_info), "b_tier": _classify(b_info), "a_rw_uuid": b_info["uuid"], "b_rw_uuid": b_info["uuid"], "chosen_uuid": b_info["uuid"], "loser_rw_uuid": None}`. No writes.
4. `a_info, _ = await _lookup_a_and_b_in_rw(a_vless_uuid=A.vless_uuid, a_email=A.email, b_short_uuid=None)` — B is already loaded, we only re-lookup A. (Implementation detail: `_lookup_a_and_b_in_rw` takes both, the by_url path can also be modeled as two calls — a single `_lookup_rw_a_side` helper is cleaner.)
5. `a_tier = _classify(a_info)`, `b_tier = _classify(b_info)`.
6. `a_rw_uuid = (a_info or {}).get("uuid")`, `b_rw_uuid = b_info["uuid"]`.
7. Call `_decide(a_tier=a_tier, t_tier=b_tier, a_rw_uuid=a_rw_uuid, t_rw_uuid=b_rw_uuid, android_id=current_user_id, tg_user_id=current_user_id)`. PRO+PRO raises `MergeBlocked` from inside `_decide` — propagate.
8. From the tuple, keep only `chosen_uuid` and `result_code`. Map result_code as-is.
9. Compute `loser_rw_uuid`: if `chosen_uuid == a_rw_uuid` → loser=B → `loser_rw_uuid = b_rw_uuid`. Else if `chosen_uuid == b_rw_uuid` → loser=A → `loser_rw_uuid = a_rw_uuid` (which is None when A had no RW user → no deactivation).
10. Apply: `A.vless_uuid = chosen_uuid`. (No FK reparenting, no DELETE — B is virtual.)
11. `await session.flush()`. Caller commits.
12. Return dict.

### Final naming decision (helper)

Use a single helper `_lookup_a_side_rw(vless_uuid, email)` that mirrors the A-lookup branch of `_lookup_rw`. B-side is one direct call to `get_user_by_short_uuid_raw` in `import_subscription_by_uuid` body — wrapping it is unnecessary. This is simpler than the `_lookup_a_and_b_in_rw` sketched above.

### `miniapp/backend/android/link_router.py` — new endpoint

```python
@router.post("/by_url", response_model=LinkByUrlResponse)
@limiter.limit("3/minute")
async def link_by_url(
    request: Request,
    payload: LinkByUrlRequest,
    user: repo.UserRow = Depends(deps.require_verified_email),
) -> LinkByUrlResponse:
    ...
```

Flow:
1. `short_uuid = _parse_short_uuid(payload.url)` — 422 `invalid_url` on failure.
2. Open `async_session()` (re-uses the bot-side sessionmaker since miniapp shares the same DB).
3. Call `import_subscription_by_uuid(s, current_user_id=user.id, b_rw_short_uuid=short_uuid)`.
   - `LookupNotFound` → `HTTPException(404, detail={"code": "rw_not_found"})`. No commit needed (nothing was written).
   - `MergeBlocked` → `await s.rollback()`, return `LinkByUrlResponse(result="both_pro_support_needed", a_tier="pro", b_tier="pro")` with HTTP 200. Body code is the contract; HTTP status reflects "we understood, here is the verdict".
   - Other `Exception` → log, `HTTPException(500, detail={"code": "internal"})`.
4. `await s.commit()`.
5. Best-effort RW deactivate if `result` ∈ {merged_pro, merged_free, ok} and `loser_rw_uuid` is not None:
   ```python
   try:
       await rem.update_user(user_uuid=merge["loser_rw_uuid"], status="disabled")
   except Exception as exc:
       logger.warning(...); await notify_log(f"⚠️ Failed to disable...")
   ```
6. `await notify_log(...)` with the unified message (format below).
7. Return `LinkByUrlResponse(result=merge["result"], a_tier=merge["a_tier"], b_tier=merge["b_tier"])`.

### URL parsing

```python
import re
from urllib.parse import urlparse

_SUBSCRIPTION_HOST = os.environ.get("SUBSCRIPTION_HOST", "sub.domain.com")
_SHORT_UUID_RE = re.compile(r"^[A-Za-z0-9_-]{8,32}$")


def _parse_short_uuid(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(422, detail={"code": "invalid_url"})
    if parsed.netloc != _SUBSCRIPTION_HOST:
        raise HTTPException(422, detail={"code": "invalid_url"})
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) != 1 or not _SHORT_UUID_RE.match(parts[0]):
        raise HTTPException(422, detail={"code": "invalid_url"})
    return parts[0]
```

Query string and fragment are ignored (`urlparse` separates them from `path`).

### Schemas — `miniapp/backend/android/schemas_data.py`

```python
class LinkByUrlRequest(BaseModel):
    url: HttpUrl


class LinkByUrlResponse(BaseModel):
    result: str    # merged_pro | merged_free | ok | already_owned | both_pro_support_needed
    a_tier: str    # pro | free | none
    b_tier: str    # pro | free  (always known when we get to a response)
```

### Notify log format

```
🔗 <b>Android sub-URL import: {result}</b>
user: <code>{user_id}</code> {email} rw=<code>{a_rw_uuid or '—'}</code> tier=<code>{a_tier}</code>
imported: rw=<code>{b_rw_uuid}</code> tier=<code>{b_tier}</code>
chosen_uuid=<code>{chosen}</code> disabled_uuid=<code>{disabled or '—'}</code>
```

For `already_owned`: same but `chosen_uuid` matches both sides and `disabled_uuid=—`.
For `both_pro_support_needed`: only the `user:` and `imported:` lines (no chosen/disabled).
For `LookupNotFound` errors at router boundary: a shorter `❌ <b>Android sub-URL import: rw_not_found</b> user=... short_uuid=...` message is sent before the 404 response.

## Transactional boundary

Single DB write (`A.vless_uuid = chosen_uuid`) inside `async with async_session() as s:`. Commit at the end. RW deactivation is best-effort, outside the transaction — if it fails, the DB still reflects the import; admins see the orphan via `notify_log`.

## Auth and rate limiting

- `Depends(deps.require_verified_email)` — same as `POST /api/android/link/start`. Unverified emails get 403. Missing/invalid JWT gets 401 from the auth dependency chain.
- `@limiter.limit("3/minute")` — same as `start_link`. URL imports are not high-frequency; this is enough to throttle credential-stuffing attempts against random short_uuids.
- No additional tier check: a FREE user is allowed to import a PRO URL (that's the point of the feature).

## Edge cases (covered by code, not just tests)

1. **A has no `email` and no `vless_uuid`** — A-side lookup returns None, `a_tier="none"`, matrix gives `ok` with chosen=B.uuid. Works.
2. **A.email present but RW returns 404** — same as #1.
3. **A.vless_uuid is set but RW returns 404 for it** — same: A-side becomes "none", chosen=B.uuid, no deactivation (no loser uuid to disable).
4. **Self-import** — short-circuit at step 3 of the flow, no writes.
5. **A user deleted between auth and merge** — `session.get(User, ...)` returns None → 500. Extremely rare race; no special handling.
6. **RW deactivate fails** — best-effort, lifted into notify_log with ⚠️.
7. **URL has query string** (`?ref=foo`) — `urlparse` drops query from `path`, validation passes.
8. **URL is `http://` not `https://`** — 422.
9. **Multi-segment path** (`/api/sN_xxx`) — 422.

## Testing strategy

### Unit tests — extend `tests/test_android_link_merge.py`

**Extend `FakeRemnawave` (in `tests/conftest.py`):**
- New parameter `short_uuid` on `add_user(...)`. Stored in `by_short_uuid: dict[str, str]` map.
- New async method `get_user_by_short_uuid_raw(short_uuid)` returning the same dict as `get_user_from_uuid` for the mapped uuid (or None).
- `fake_remnawave` fixture monkeypatches `app.api.remnawave.api.get_user_by_short_uuid_raw` (add export to shim if missing — see Open Tasks).

**Open Tasks (must be checked first by implementer):**
- Verify `app.api.remnawave.api` exposes `get_user_by_short_uuid_raw`. If not, add a one-line shim mirroring `get_user_from_uuid`. Check `miniapp/backend/remnawave_client.py:88-95` for the existing miniapp shim — the bot-side `app/api/remnawave/api.py` may need the same.

**New class `TestImportSubscriptionByUuid`:**

1. **PRO A + FREE B → merged_pro, A.uuid kept, B.uuid disabled.**
2. **FREE A + PRO B → merged_pro, B.uuid kept, A.uuid disabled.**
3. **FREE A + FREE B → merged_free, B.uuid kept, A.uuid disabled.**
4. **PRO A + PRO B → `MergeBlocked` raised, A.vless_uuid unchanged, no RW calls.**
5. **A.tier=none + B FREE → ok, B.uuid kept, no deactivation** (A.vless_uuid was None and A.email had no RW user).
6. **A.tier=none + B PRO → ok, B.uuid kept, no deactivation.**
7. **Self-import: A.vless_uuid == B.uuid → already_owned, no writes, no RW disable calls.**
8. **`get_user_by_short_uuid_raw` returns None → `LookupNotFound`, no writes.**
9. **A.vless_uuid is None but A.email resolves to PRO via `get_user_from_email` → ok branch with chosen=A.uuid** (verifies email-fallback lookup).

### Router tests — new file `tests/test_link_by_url_router.py`

Uses FastAPI `TestClient`. New fixture `link_by_url_client` constructs a minimal `FastAPI` app importing the router, overriding `deps.require_verified_email` to return a fake `UserRow`. Mocks `notify_log` and `get_user_by_short_uuid_raw`. Uses `with_app_db` to redirect the session factory.

10. **POST with valid URL + merged_pro outcome → 200, body `{"result": "merged_pro", "a_tier": "pro", "b_tier": "free"}`.**
11. **Invalid host → 422 `{"detail": {"code": "invalid_url"}}`.**
12. **Multi-segment path → 422.**
13. **`http://` scheme → 422.**
14. **`LookupNotFound` (RW returns None) → 404 `{"detail": {"code": "rw_not_found"}}`.**
15. **`MergeBlocked` → 200 `{"result": "both_pro_support_needed", ...}`.**
16. **Unauthenticated → 401** (dependency override removed for this test).
17. **Email not verified → 403.**
18. **`notify_log` called once with `Android sub-URL import: merged_pro` in the text.**
19. **Self-import URL → 200 `{"result": "already_owned", ...}`, `disabled_calls == []`.**

### Out of scope for tests

- HTML escaping of notify_log (covered by tg-link tests).
- Concurrent imports of the same short_uuid (RW deactivate is idempotent).
- Pydantic HttpUrl validation (stdlib).
- Rate-limit behavior (covered separately by existing slowapi tests in this repo if any).

### Verification commands

```bash
python -m pytest tests/test_android_link_merge.py -v
python -m pytest tests/test_link_by_url_router.py -v
python -m pytest packages/common_db/tests/ -q
```

**Known limitation:** running `pytest tests/ packages/common_db/tests/` jointly fails with `ModuleNotFoundError: No module named 'tests.test_X'` due to a name collision (`tests/__init__.py` + the `packages/common_db/tests` package use the same `tests` namespace). Workaround: run the two directories separately. Same issue documented in the tg-link feature work.

## Files touched

| Path | Change |
|---|---|
| `app/handlers/android_link_merge.py` | add `LookupNotFound`, `_lookup_a_side_rw`, `import_subscription_by_uuid` |
| `app/api/remnawave/api.py` | add `get_user_by_short_uuid_raw` shim if missing |
| `miniapp/backend/android/link_router.py` | add `POST /by_url`, `_parse_short_uuid` helper |
| `miniapp/backend/android/schemas_data.py` | add `LinkByUrlRequest`, `LinkByUrlResponse` |
| `tests/conftest.py` | extend `FakeRemnawave` with `short_uuid` + `get_user_by_short_uuid_raw` |
| `tests/test_android_link_merge.py` | add `TestImportSubscriptionByUuid` (9 cases) |
| `tests/test_link_by_url_router.py` | **new** — router-level integration (10 cases) |

## Out of scope

- Reversing the import ("undo"). No UX request for it; user can re-import via the original URL if they kept it.
- Bulk import (multiple URLs at once).
- Importing without authentication (e.g., a URL-only deep-link). Adding the imported subscription requires an existing app account.
- Migrating across the legacy `support_bot.sqlite3` — unrelated to subscriptions.
- Notifying user B (the original owner of the imported subscription) that someone took it over. The URL is a bearer credential; if A has it, they're entitled to act.

## Risks (non-blocking)

1. **URL leakage as silent account takeover.** Anyone with the URL can take the subscription via this endpoint. Mitigation: `require_verified_email` adds a small barrier (attacker needs an account with a verified mailbox). Rate limit `3/min` slows credential-stuffing against short_uuids. Document in user-facing copy: "treat your subscription URL like a password".
2. **Orphan RW users** after deactivation. Same drift as the tg-link feature; `app/admin/sub_clean.py` can be extended for cleanup.
3. **Pydantic `HttpUrl` is strict about percent-encoding.** Some clients may send URLs with raw `:` in path. If we hit this in production, we can swap to `str` + manual validation; not anticipated.
