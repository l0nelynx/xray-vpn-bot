# Android subscription import by URL — email confirmation

**Date:** 2026-05-21
**Scope:** Strengthens the just-landed `POST /api/android/link/by_url` endpoint by adding mandatory email confirmation. Touches `app/handlers/android_link_merge.py:308` (`import_subscription_by_uuid` signature), `miniapp/backend/android/schemas_data.py` (`LinkByUrlRequest`), `miniapp/backend/android/link_router.py` (call site + notify_log on mismatch), and the existing test files.
**Builds on:** `docs/superpowers/specs/2026-05-21-android-link-by-url-design.md`. This spec amends, it does not replace.

## Problem

The endpoint shipped today (commit `da83c27`) lets any holder of a Remnawave subscription URL take that subscription over, gated only by `require_verified_email` and a 3/min rate limit. The original spec called this out as Risk #1: "URL leakage as silent account takeover. Anyone with the URL can take the subscription via this endpoint."

We add a second knowledge factor: the user must supply the email address of the subscription's original owner. The endpoint compares it against the email Remnawave has on file. URL alone is no longer enough; an attacker who scraped a URL from a forum still needs to know the buyer's email.

## What changes

### 1. Request schema — `miniapp/backend/android/schemas_data.py`

```python
from pydantic import BaseModel, EmailStr


class LinkByUrlRequest(BaseModel):
    url: str       # validated by _parse_short_uuid in the router
    email: EmailStr  # owner's email; compared against Remnawave's value
```

`EmailStr` does Pydantic's standard RFC-5322 light validation. Malformed email → 422 from FastAPI before any RW or DB work happens.

### 2. Merge function — `app/handlers/android_link_merge.py:308`

New required keyword argument:

```python
async def import_subscription_by_uuid(
    session,
    *,
    current_user_id: int,
    b_rw_short_uuid: str,
    claimed_email: str,            # NEW — required
) -> dict[str, Any]:
```

After the `get_user_by_short_uuid_raw` lookup, **before** the self-import short-circuit:

```python
rw_email = (b_info.get("email") or "").strip().lower()
if not rw_email or rw_email != claimed_email.strip().lower():
    logger.info(
        "import_subscription_by_uuid: email_mismatch user=%s "
        "short=%s rw_email=%s claimed=%s",
        current_user_id, b_rw_short_uuid,
        rw_email or "<none>", claimed_email,
    )
    raise LookupNotFound(b_rw_short_uuid)
```

Key points:
- `strip().lower()` on both sides — email addresses are case-insensitive in the local-part per RFC 5321 §2.4 in practice (Gmail, etc. treat them so). Leading/trailing whitespace from the client is normalized away.
- RW returning empty/None email → reject (no anchor to compare against → can't confirm).
- The new exception type is `LookupNotFound` — the same one used when RW returns no user. The router maps both to **HTTP 404 `rw_not_found`**. From the wire, an attacker cannot tell "URL is invalid" from "URL is valid but you don't know the owner's email."
- Internal log message records the reason (`email_mismatch`) so we can debug.

### 3. Router — `miniapp/backend/android/link_router.py`

The call gets one extra kwarg:

```python
merge = await import_subscription_by_uuid(
    s,
    current_user_id=user.id,
    b_rw_short_uuid=short_uuid,
    claimed_email=payload.email,
)
```

The existing `LookupNotFound` branch already produces the right HTTP response (404 `rw_not_found`). The branch's notify_log message gets a small upgrade so admins can distinguish the two reasons in the alert stream — the wire response stays opaque:

```python
pending_notify = (
    f"❌ <b>Android sub-URL import: rw_not_found</b>\n"
    f"user=<code>{user.id}</code> "
    f"short_uuid=<code>{esc(short_uuid)}</code>\n"
    f"claimed_email=<code>{esc(payload.email)}</code>"
)
```

Distinguishing reasons in ops:
- The wire is uniform (both raise `LookupNotFound` → both produce the same 404 body).
- `logger.info` inside the merge function records `email_mismatch user=… rw_email=… claimed=…` on the mismatch branch; nothing similar on the pure short-uuid-miss branch. Admins reading the server log can tell them apart.
- `notify_log` always carries `claimed_email`; the absence of a corresponding RW user in admin's recollection is the second hint.

Adding a discriminator inside `LookupNotFound` would leak the distinction back into the test/log surface and is YAGNI until we see actual admin pain.

### 4. Self-import behavior

Email check runs **before** the self-import short-circuit. Concrete effect:
- User pastes their own URL with the right email → 200 `already_owned`.
- User pastes their own URL with the wrong email → 404 `rw_not_found`.

This is deliberate (Q3 above). The endpoint becomes a uniform "prove you know the email" gate; there is no secret bypass for already-owned URLs.

## Resolution flow (updated)

1. Parse `short_uuid` from `payload.url` → 422 `invalid_url` on shape failure.
2. Open `async_session()`.
3. `b_info = await rem.get_user_by_short_uuid_raw(short_uuid)`. None → `LookupNotFound` → 404.
4. **Email check.** Mismatch or RW email empty → `LookupNotFound` → 404.
5. Self-import check (A.vless_uuid == B.uuid) → return `already_owned`.
6. A-side RW lookup, classify, decide, write, flush.
7. Caller commits.

## Error matrix (wire-visible)

| Condition | HTTP | Body |
|---|---|---|
| URL shape invalid (host/scheme/path/regex) | 422 | `{"detail": {"code": "invalid_url"}}` |
| Email malformed per `EmailStr` | 422 | Pydantic validation envelope |
| RW returns no user for short_uuid | 404 | `{"detail": {"code": "rw_not_found"}}` |
| RW user found, email mismatch | 404 | `{"detail": {"code": "rw_not_found"}}` (same as above — by design) |
| RW user found, RW email is empty | 404 | `{"detail": {"code": "rw_not_found"}}` (same) |
| Both sides PRO | 200 | `{"result": "both_pro_support_needed", ...}` |
| Self-import (email matches) | 200 | `{"result": "already_owned", ...}` |
| Merge succeeds | 200 | `{"result": "merged_pro\|merged_free\|ok", ...}` |

## What does NOT change

- `LinkByUrlResponse` — same three fields (`result`, `a_tier`, `b_tier`).
- The PRO/FREE matrix and `_decide` — untouched.
- The best-effort RW deactivate of `loser_rw_uuid` — same.
- Rate limit `3/minute` — same. The email factor by itself doesn't justify loosening it; brute-forcing email when you already have a URL is plausible only if the email pool is small (e.g. one tenant), and the limit still slows that.
- Auth (`require_verified_email`) — same.

## Why this is a worthwhile defense

The attacker's prerequisites go from "I scraped a URL" to "I scraped a URL **and** I know the buyer's email." Subscription URLs leak through:
- Screenshots posted to chats
- Browser history sync
- Clipboard-reading apps
- Forum posts asking for help

Email rarely travels with the URL through those channels. A buyer who tells a stranger "here's my sub URL" almost never adds "...and my email is X@Y."

Email is still not a password — it isn't secret in absolute terms. This is defense-in-depth, not bulletproofing. The defense is good enough that opportunistic URL pickup stops working, and a targeted attack now needs reconnaissance the attacker may not be able to do.

## Tests

### Unit-merge — `tests/test_android_link_merge.py::TestImportSubscriptionByUuid` (extend existing class)

All existing 9 tests in this class need their call sites updated to pass `claimed_email=<the RW user's email>`. Without this, every test would now fail with `LookupNotFound`.

Add five new tests:

1. **`test_email_mismatch_raises_lookup_not_found`** — B exists with `email="b@x.io"`, `claimed_email="other@x.io"` → `LookupNotFound`, no DB write, no A-side RW lookup (verify: `fake_remnawave.disabled_calls == []` and A.vless_uuid unchanged).
2. **`test_rw_email_missing_raises_lookup_not_found`** — B exists but `email=None`, any `claimed_email` → `LookupNotFound`.
3. **`test_email_match_case_and_whitespace_insensitive`** — B has `email="Alice@X.IO"`, `claimed_email="  alice@x.io  "` → merge proceeds.
4. **`test_self_import_with_wrong_email_raises_lookup_not_found`** — A.vless_uuid == B.uuid (would short-circuit to `already_owned`), but `claimed_email` doesn't match B's email → `LookupNotFound`. Demonstrates email check runs before self-import.
5. **`test_self_import_with_right_email_returns_already_owned`** — same setup, correct email → `already_owned`.

### Router — `tests/test_link_by_url_router.py::TestLinkByUrlEndpoint` (extend)

All existing 10 endpoint tests need `"email": "a@x.io"` (matching what `fake_remnawave.add_user` was set to in each test). Update them in place.

Add four new tests:

6. **`test_missing_email_returns_422`** — `json={"url": URL}` (no email field) → 422 (Pydantic).
7. **`test_malformed_email_returns_422`** — `json={"url": URL, "email": "not-an-email"}` → 422 (Pydantic).
8. **`test_email_mismatch_returns_404`** — RW B has `email="b@x.io"`, request sends `email="other@x.io"` → 404 `{"detail": {"code": "rw_not_found"}}`. Identical to `test_rw_lookup_miss_returns_404`'s response — by design.
9. **`test_email_mismatch_notify_includes_claimed_email`** — same setup as #8; verify `notify_calls` contains the claimed email so admins can distinguish reasons in their alert stream.

### Existing tests that stay untouched

- The 11 `TestParseShortUuid` tests in the same file — pure URL parser, no email involvement.
- All other test files.

## Transactional boundary

Email check happens **before** `session.flush()` and before any RW write. A mismatch performs zero writes. No need for `s.rollback()` because nothing was modified — though the existing router code already calls `s.rollback()` in the `LookupNotFound` branch, which remains a defensive no-op (cheap, clear).

## Risks (revised)

1. **~~URL leakage as silent account takeover.~~** Reduced from "anyone with URL" to "anyone with URL **and** the owner's email." Material improvement.
2. **Oracle risk.** The 404 is uniform across "URL invalid", "URL valid but email wrong", and "URL valid but RW email empty." An attacker can confirm a URL is valid only by guessing the right email — which is the same as a successful attack, so they gain nothing from probing.
3. **Internal logs leak the distinction.** `notify_log` and `logger.info` differentiate email_mismatch from short_uuid_miss for ops. This is intentional and not wire-visible.
4. **EmailStr depends on `email-validator`.** Already a project dep (Pydantic v2 requires it for `EmailStr`). Verify on the implementer side that `pip show email-validator` returns something; if not, add it. (Almost certainly already there — Pydantic v2 ships it.)
5. **Future contract evolution.** If we ever need to differentiate email_mismatch on the wire (for legit UX), add a discriminator to `LookupNotFound` then. Don't pre-build it.

## Out of scope

- Notifying user B (the URL's original owner) that someone attempted/succeeded the import. The original spec already chose not to do this; that decision stands.
- Email confirmation for the Telegram-link flow (`POST /api/android/link/start`). That flow is a different threat model: the user proves they control a Telegram account, not that they own a URL.
- Replacing email confirmation with a stronger factor (HMAC of `(short_uuid, secret)` baked into Remnawave). Bigger architectural change; out of scope.
- Rate-limit tightening. The current 3/min is the same as `start_link` and is fine.

## Files touched (summary)

| Path | Change |
|---|---|
| `miniapp/backend/android/schemas_data.py` | `LinkByUrlRequest.email: EmailStr` |
| `app/handlers/android_link_merge.py` | `import_subscription_by_uuid` takes `claimed_email`; email-compare branch raises `LookupNotFound` |
| `miniapp/backend/android/link_router.py` | pass `claimed_email=payload.email` to merge call; notify_log on rw_not_found mentions `claimed_email` |
| `tests/test_android_link_merge.py` | update 9 existing tests + add 5 |
| `tests/test_link_by_url_router.py` | update 10 existing tests + add 4 |

## Verification

```bash
python -m pytest tests/test_android_link_merge.py -v
python -m pytest tests/test_link_by_url_router.py -v
python -m pytest packages/common_db/tests/ -q
```

Expected after implementation: 47 + 5 = 52 merge tests, 11 + 10 + 4 = 25 router tests, 186 common_db tests.
