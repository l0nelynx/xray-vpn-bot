# Android Link by URL — Email Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `POST /api/android/link/by_url` require a `claimed_email` field that must match the Remnawave-side email of the URL's owner before any merge happens. Email mismatch and RW-side missing email both produce an opaque `404 rw_not_found` — the wire response is uniform with the existing "URL not found" case so the endpoint isn't an oracle.

**Architecture:** Add a required field to `LinkByUrlRequest`, thread it through `import_subscription_by_uuid` as a new required kwarg, do the case- and whitespace-insensitive compare immediately after the B-side RW lookup (before self-import short-circuit), and raise the existing `LookupNotFound` on mismatch. Log the distinguishing reason (`email_mismatch`) inside `logger.info` and a one-line `notify_log` enrichment so ops can tell the two reasons apart in their own tools.

**Tech Stack:** Pydantic `EmailStr` for format validation, existing `app/handlers/android_link_merge.py` flow, existing `miniapp/backend/android/link_router.py` endpoint, no new dependencies (`email-validator 2.3.0` is already installed).

---

## File Structure

**Modified files:**
- `miniapp/backend/android/schemas_data.py` — switch `LinkByUrlRequest.url: str` → add a sibling `email: EmailStr` (one line).
- `app/handlers/android_link_merge.py` — `import_subscription_by_uuid` gets a new required `claimed_email: str` kwarg and an email-compare branch that raises `LookupNotFound`.
- `miniapp/backend/android/link_router.py` — pass `claimed_email=payload.email` into the merge call; extend the `LookupNotFound` notify_log message with `claimed_email`.
- `tests/test_android_link_merge.py` — update 9 existing tests in `TestImportSubscriptionByUuid` to seed B with an email and pass `claimed_email`; add 5 new tests covering mismatch/case-insensitivity/self-import-with-wrong-email.
- `tests/test_link_by_url_router.py` — update 10 existing endpoint tests to send `"email": ...` in the body and seed B's RW email; add 4 new tests covering missing-email/malformed/mismatch/notify-content.

Each unit has one clear responsibility:
- `schemas_data.py` owns the wire contract.
- `android_link_merge.py` owns the email-vs-RW comparison logic (single place, single source of truth).
- `link_router.py` is pure glue — forwards the new field, enriches the failure notify.

---

## Pre-flight facts

Before starting, the implementer should know:

1. **`email-validator` is installed.** `python -c "import email_validator; print(email_validator.__version__)"` → `2.3.0`. So `from pydantic import EmailStr` works without additional setup.
2. **`LookupNotFound` already exists** at `app/handlers/android_link_merge.py:74` and takes a single `short_uuid: str` argument — we reuse it as-is.
3. **`FakeRemnawave.add_user(...)` already accepts `email=` and `short_uuid=`** (verified in `tests/conftest.py:60-80`). Make sure every existing test that needs B's email now passes it; some tests today only set `uuid` and `short_uuid`.
4. **Tests use `_asyncio.run(...)` not `asyncio.run`** in `tests/test_android_link_merge.py` (it's imported as `import asyncio as _asyncio` near the top). In `tests/test_link_by_url_router.py` it's plain `asyncio`. Follow whichever style the file you're editing uses.
5. **Existing self-import test currently does not pass `email` to B's RW entry** (it does — line 720 — `email="a@x.io"`). That test still works because A's email matches by accident. We need a new test where they intentionally diverge.
6. **The router test fixture sets `_FakeUser.email = "a@x.io"`** (`tests/test_link_by_url_router.py:90`) — this is **A's email** (the authenticated user). Don't confuse it with the `claimed_email` field, which is the **subscription owner's** email passed in the request body. They may or may not be the same address; they're independent inputs.

---

## Task 1: Add `email: EmailStr` to `LinkByUrlRequest`

**Files:**
- Modify: `miniapp/backend/android/schemas_data.py:86-89` (the `LinkByUrlRequest` class).

This is a contract change. Done in isolation so existing tests stay green until Task 2 (which is when they would start failing).

- [ ] **Step 1: Verify pydantic.EmailStr is importable**

Run:
```bash
python -c "from pydantic import EmailStr; print(EmailStr)"
```
Expected: `<class 'pydantic.networks.EmailStr'>` — no import error.

- [ ] **Step 2: Update the schema**

Edit `miniapp/backend/android/schemas_data.py`. Replace this block (currently around lines 9-10 for the import and lines 86-89 for the class):

```python
from pydantic import BaseModel
```

…with:

```python
from pydantic import BaseModel, EmailStr
```

…and replace this block:

```python
class LinkByUrlRequest(BaseModel):
    url: str  # Validated by _parse_short_uuid in the router; plain str
              # avoids Pydantic HttpUrl's strict percent-encoding edge
              # cases (some clients send raw `:` in path).
```

…with:

```python
class LinkByUrlRequest(BaseModel):
    url: str  # Validated by _parse_short_uuid in the router; plain str
              # avoids Pydantic HttpUrl's strict percent-encoding edge
              # cases (some clients send raw `:` in path).
    email: EmailStr  # Subscription owner's email — must match the email
                     # Remnawave has on file for the URL's owner. See
                     # docs/superpowers/specs/2026-05-21-android-link-by-url-email-design.md.
```

- [ ] **Step 3: Verify the import resolves**

Run:
```bash
python -c "from miniapp.backend.android.schemas_data import LinkByUrlRequest; print(LinkByUrlRequest.model_fields)"
```
Expected output includes both `'url'` and `'email'` keys, and `'email'`'s annotation references `EmailStr`.

- [ ] **Step 4: Verify the existing test suite is now red where expected**

The existing endpoint tests don't pass `email` — Pydantic should now 422 them.

Run:
```bash
python -m pytest tests/test_link_by_url_router.py::TestLinkByUrlEndpoint -v
```
Expected: most tests fail or 422 because the body is missing `email`. This is intentional — Task 4 will fix them. Do not commit yet if anything else is unexpectedly broken; if a parser-only test (`TestParseShortUuid`) breaks, stop and investigate (none should — it doesn't touch the schema).

- [ ] **Step 5: Commit**

```bash
git add miniapp/backend/android/schemas_data.py
git commit -m "feat(miniapp): add required email field to LinkByUrlRequest

LinkByUrlRequest gains an EmailStr 'email' field. The router will
forward it to import_subscription_by_uuid in a follow-up commit;
tests are updated in the same series.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Add `claimed_email` kwarg + email-compare branch to `import_subscription_by_uuid`

**Files:**
- Modify: `app/handlers/android_link_merge.py:308-411` (the `import_subscription_by_uuid` function).
- Test: `tests/test_android_link_merge.py::TestImportSubscriptionByUuid` (existing class, line 549) — we update the existing 9 tests + add 5 new ones across Tasks 2 and 3.

This is the heart of the change. Split into two: **2a** updates the 9 existing tests and the function signature so the old behavior keeps working, **2b** adds the email-rejection branch + the 5 new tests.

### Task 2a: Add the kwarg + thread it through existing tests

- [ ] **Step 1: Update the function signature**

In `app/handlers/android_link_merge.py:308-313`, change:

```python
async def import_subscription_by_uuid(
    session,
    *,
    current_user_id: int,
    b_rw_short_uuid: str,
) -> dict[str, Any]:
```

…to:

```python
async def import_subscription_by_uuid(
    session,
    *,
    current_user_id: int,
    b_rw_short_uuid: str,
    claimed_email: str,
) -> dict[str, Any]:
```

Also update the docstring around line 314 to mention `claimed_email`. Replace the existing docstring body's first paragraph with:

```python
    """Import a Remnawave subscription URL into the current user's account.

    A = current user (must exist in DB).
    B = subscription owner identified by Remnawave short_uuid (may not exist
        in our DB — only RW is consulted for B).

    `claimed_email` is the email the requester claims belongs to B. It is
    compared case- and whitespace-insensitively to B's RW-side email
    immediately after the RW lookup; a mismatch (or an empty RW email)
    raises `LookupNotFound` — the same opaque failure used when the
    short_uuid resolves to nothing. See
    docs/superpowers/specs/2026-05-21-android-link-by-url-email-design.md.
```

- [ ] **Step 2: Update the existing 9 tests to pass `claimed_email`**

This is mechanical but tedious. For each test in `TestImportSubscriptionByUuid`, do TWO things:

(a) make sure `fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT, ...)` includes `email="b@x.io"` (or any plausible email — pick `b@x.io` for consistency).
(b) add `claimed_email="b@x.io"` to the `import_subscription_by_uuid(...)` call (or the equivalent — see helper below).

The class has a `_run` helper (line 554) that does the call. Update it to accept and forward `claimed_email`:

```python
    def _run(self, session_factory, *, current_user_id, short_uuid,
             claimed_email):
        async def go():
            async with session_factory() as s:
                result = await import_subscription_by_uuid(
                    s,
                    current_user_id=current_user_id,
                    b_rw_short_uuid=short_uuid,
                    claimed_email=claimed_email,
                )
                await s.commit()
                survivor = await s.get(User, current_user_id)
                return result, survivor.vless_uuid

        return _asyncio.run(go())
```

Then per-test changes:

**`test_pro_a_free_b_keeps_a_disables_b`** (line 568):
- B's `add_user(...)` already lacks email; add `email="b@x.io"`.
- The `self._run(...)` call needs `claimed_email="b@x.io"`.

**`test_free_a_pro_b_keeps_b_disables_a`** (line 593):
- Add `email="b@x.io"` to B's add_user.
- Add `claimed_email="b@x.io"` to the _run call.

**`test_free_a_free_b_keeps_b_disables_a`** (line 618):
- Add `email="b@x.io"` to B's add_user.
- Add `claimed_email="b@x.io"` to the _run call.

**`test_pro_a_pro_b_raises_merge_blocked_no_writes`** (line 642):
- Add `email="b@x.io"` to B's add_user.
- The test calls `import_subscription_by_uuid(...)` directly inside an async block (line 656-661); add `claimed_email="b@x.io"` to that call.

**`test_a_none_b_free_simple_takeover`** (line 670):
- Add `email="b@x.io"` to B's add_user.
- Add `claimed_email="b@x.io"` to the _run call.

**`test_a_none_b_pro_simple_takeover`** (line 694):
- Add `email="b@x.io"` to B's add_user.
- Add `claimed_email="b@x.io"` to the _run call.

**`test_self_import_short_circuits`** (line 716):
- B has `email="a@x.io"` (line 720) — keep it; A's email also `a@x.io` (line 725).
- Add `claimed_email="a@x.io"` to the _run call (must match B's RW email).

**`test_b_not_found_raises_lookup_not_found`** (line 740):
- No B in RW, so no email to set.
- The test calls `import_subscription_by_uuid(...)` directly inside an async block (line 749-754); add `claimed_email="b@x.io"` (any value — the function should raise before checking email since RW returns None).

**`test_a_email_fallback_when_vless_uuid_missing`** (line 761):
- Add `email="b@x.io"` to B's add_user.
- Add `claimed_email="b@x.io"` to the _run call.

- [ ] **Step 3: Run merge tests, expect them to PASS (function still does no email check yet)**

Run:
```bash
python -m pytest tests/test_android_link_merge.py::TestImportSubscriptionByUuid -v
```
Expected: 9 passed. The new `claimed_email` kwarg is accepted but unused — tests just verify the signature change and seeded emails don't break anything.

(If any test fails, the issue is in the test rewiring, not the production code. Fix and re-run.)

- [ ] **Step 4: Commit (intermediate — kwarg only, no enforcement yet)**

```bash
git add app/handlers/android_link_merge.py tests/test_android_link_merge.py
git commit -m "refactor(android-link): add claimed_email kwarg to import_subscription_by_uuid

Plumbing only — the parameter is accepted but not yet enforced.
Tests updated to pass it. Next commit adds the email-compare branch.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 2b: Add the email-compare branch + 5 new tests

- [ ] **Step 1: Write the 5 failing tests**

Append to `TestImportSubscriptionByUuid` in `tests/test_android_link_merge.py`. The 9 existing tests end around line 790; append after them.

```python
    def test_email_mismatch_raises_lookup_not_found(
        self, session_factory, fake_remnawave,
    ):
        """B exists in RW with email b@x.io; client claims other@x.io.
        Must raise LookupNotFound BEFORE any A-side RW lookup or DB write.
        """
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                email="b@x.io",
                                status="active",
                                data_limit=10 * 1024 ** 3)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid"))
                await s.commit()
        _asyncio.run(seed())

        async def go():
            async with session_factory() as s:
                with pytest.raises(LookupNotFound):
                    await import_subscription_by_uuid(
                        s,
                        current_user_id=100,
                        b_rw_short_uuid=self.SHORT,
                        claimed_email="other@x.io",
                    )
                survivor = await s.get(User, 100)
                return survivor.vless_uuid

        vless = _asyncio.run(go())
        assert vless == "a-uuid"  # A.vless_uuid unchanged
        assert fake_remnawave.disabled_calls == []  # no RW deactivate

    def test_rw_email_missing_raises_lookup_not_found(
        self, session_factory, fake_remnawave,
    ):
        """B exists in RW but with email=None. No claimed_email can match.
        Must raise LookupNotFound.
        """
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                email=None,
                                status="active",
                                data_limit=10 * 1024 ** 3)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid"))
                await s.commit()
        _asyncio.run(seed())

        async def go():
            async with session_factory() as s:
                with pytest.raises(LookupNotFound):
                    await import_subscription_by_uuid(
                        s,
                        current_user_id=100,
                        b_rw_short_uuid=self.SHORT,
                        claimed_email="anything@x.io",
                    )

        _asyncio.run(go())

    def test_email_match_case_and_whitespace_insensitive(
        self, session_factory, fake_remnawave,
    ):
        """B's RW email is 'Alice@X.IO'; client sends '  alice@x.io  '.
        Must succeed.
        """
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                email="Alice@X.IO",
                                status="active",
                                data_limit=10 * 1024 ** 3)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, tg_id=55))  # A is "none" tier
                await s.commit()
        _asyncio.run(seed())

        result, vless = self._run(
            session_factory,
            current_user_id=100,
            short_uuid=self.SHORT,
            claimed_email="  alice@x.io  ",
        )
        assert result["result"] == "ok"
        assert result["chosen_uuid"] == "b-uuid"
        assert vless == "b-uuid"

    def test_self_import_with_wrong_email_raises_lookup_not_found(
        self, session_factory, fake_remnawave,
    ):
        """A.vless_uuid == B.uuid (would short-circuit to already_owned),
        but claimed_email doesn't match B's RW email. Email check must run
        BEFORE the self-import short-circuit, so this raises LookupNotFound.
        """
        fake_remnawave.add_user(uuid="a-uuid", short_uuid=self.SHORT,
                                email="a@x.io",
                                status="active", data_limit=None)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid"))
                await s.commit()
        _asyncio.run(seed())

        async def go():
            async with session_factory() as s:
                with pytest.raises(LookupNotFound):
                    await import_subscription_by_uuid(
                        s,
                        current_user_id=100,
                        b_rw_short_uuid=self.SHORT,
                        claimed_email="wrong@x.io",
                    )

        _asyncio.run(go())

    def test_self_import_with_right_email_returns_already_owned(
        self, session_factory, fake_remnawave,
    ):
        """Self-import with matching email proceeds normally to already_owned."""
        fake_remnawave.add_user(uuid="a-uuid", short_uuid=self.SHORT,
                                email="a@x.io",
                                status="active", data_limit=None)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid"))
                await s.commit()
        _asyncio.run(seed())

        result, vless = self._run(
            session_factory,
            current_user_id=100,
            short_uuid=self.SHORT,
            claimed_email="a@x.io",
        )
        assert result["result"] == "already_owned"
        assert vless == "a-uuid"
```

- [ ] **Step 2: Run new tests, verify they fail correctly**

Run:
```bash
python -m pytest tests/test_android_link_merge.py::TestImportSubscriptionByUuid -v
```
Expected: the 9 existing tests pass; the 5 new tests fail.
- `test_email_mismatch_raises_lookup_not_found` → fails (no exception raised; the function happily proceeds with the wrong email)
- `test_rw_email_missing_raises_lookup_not_found` → fails (same)
- `test_email_match_case_and_whitespace_insensitive` → passes (the function doesn't check email at all yet)
- `test_self_import_with_wrong_email_raises_lookup_not_found` → fails (function short-circuits to already_owned)
- `test_self_import_with_right_email_returns_already_owned` → passes

This mixed-pass state confirms the tests are wired correctly — the implementation gap is exactly what we expect.

- [ ] **Step 3: Add the email-compare branch in `import_subscription_by_uuid`**

In `app/handlers/android_link_merge.py`, find the block (currently lines 350-352):

```python
    b_info = await rem.get_user_by_short_uuid_raw(b_rw_short_uuid)
    if b_info is None:
        raise LookupNotFound(b_rw_short_uuid)

    b_rw_uuid = b_info["uuid"]
```

Replace it with:

```python
    b_info = await rem.get_user_by_short_uuid_raw(b_rw_short_uuid)
    if b_info is None:
        raise LookupNotFound(b_rw_short_uuid)

    # Email confirmation gate — wire response is uniform with "short_uuid
    # not found" so the endpoint cannot be used as an oracle.
    rw_email = (b_info.get("email") or "").strip().lower()
    claimed = claimed_email.strip().lower()
    if not rw_email or rw_email != claimed:
        logger.info(
            "import_subscription_by_uuid: email_mismatch user=%s short=%s "
            "rw_email=%s claimed=%s",
            current_user_id, b_rw_short_uuid,
            rw_email or "<none>", claimed_email,
        )
        raise LookupNotFound(b_rw_short_uuid)

    b_rw_uuid = b_info["uuid"]
```

- [ ] **Step 4: Run all `TestImportSubscriptionByUuid` tests, expect all 14 to pass**

Run:
```bash
python -m pytest tests/test_android_link_merge.py::TestImportSubscriptionByUuid -v
```
Expected: 14 passed (9 existing + 5 new).

- [ ] **Step 5: Run the full merge test suite, no regressions elsewhere**

Run:
```bash
python -m pytest tests/test_android_link_merge.py -v
```
Expected: 52 passed (47 prior + 5 new).

- [ ] **Step 6: Commit**

```bash
git add app/handlers/android_link_merge.py tests/test_android_link_merge.py
git commit -m "feat(android-link): enforce email confirmation in import_subscription_by_uuid

Compares claimed_email against b_info['email'] (case- and whitespace-
insensitive). Mismatch or RW-side empty email raises LookupNotFound —
the same opaque failure used when the short_uuid resolves to nothing,
so the wire cannot be used as an oracle. Check runs before the
self-import short-circuit: no secret bypass via your own URL.

Adds 5 tests covering mismatch, missing RW email, case/whitespace
normalization, and self-import-with-wrong-email.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Wire `claimed_email` through the router + enrich notify_log

**Files:**
- Modify: `miniapp/backend/android/link_router.py:149-165` (the `link_by_url` endpoint body — the call to `import_subscription_by_uuid` and the LookupNotFound branch's `pending_notify`).
- Test: `tests/test_link_by_url_router.py::TestLinkByUrlEndpoint` (existing class, around line 155) — update 10 existing tests and add 4 new ones.

### Task 3a: Update the 10 existing endpoint tests

- [ ] **Step 1: Update each existing endpoint test to send the email field and seed B's RW email**

Open `tests/test_link_by_url_router.py`. The class starts around line 155.

For each test that hits the endpoint, modify the `link_by_url_client.post(...)` JSON body to include `"email": "<owner-email>"`, and (if the test seeds a B-side RW user) make sure that B-side user has `email=<same-value>` in its `fake_remnawave.add_user(...)`.

Use `"email": "b@x.io"` consistently — same convention as Task 2.

Concrete per-test edits:

**`test_merged_pro_returns_200_and_disables_loser`** (around line 165):
- Existing: `fake_remnawave.add_user(uuid="b-uuid", short_uuid=SHORT, status="active", data_limit=10*1024**3)` — add `email="b@x.io"`.
- Existing: `json={"url": URL}` — change to `json={"url": URL, "email": "b@x.io"}`.

**`test_invalid_url_returns_422`** (around line 198):
- No B-side seed. The URL is invalid, but we want the 422 to come from `_parse_short_uuid` inside the handler — that means the body must pass Pydantic validation first, so the `email` field must be syntactically valid. Supply `"email": "b@x.io"`: `json={"url": "https://attacker.example.com/sN_xxxxxxxxxxxx", "email": "b@x.io"}`.

**`test_multi_segment_path_returns_422`** (around line 208):
- Same — add `"email": "b@x.io"` to the JSON.

**`test_http_scheme_returns_422`** (around line 217):
- Same — add `"email": "b@x.io"` to the JSON.

**`test_rw_lookup_miss_returns_404`** (around line 226):
- No B in RW, so no email to seed. Add `"email": "b@x.io"` to the JSON — the function should raise `LookupNotFound` from the RW miss before email is checked.

**`test_both_pro_returns_200_with_support_code`** (around line 237):
- Add `email="b@x.io"` to B's add_user.
- Add `"email": "b@x.io"` to the JSON.

**`test_self_import_returns_already_owned`** (around line 266):
- B-side: `add_user(uuid="a-uuid", email="a@x.io", short_uuid=SHORT, ...)` — already has email.
- Add `"email": "a@x.io"` to the JSON (matches B's email — which is the same as A's because it's a self-import).

**`test_email_not_verified_returns_403`** (around line 283):
- Add `"email": "b@x.io"` to the JSON.

**`test_missing_auth_dependency_returns_401`** (around line 305):
- Add `"email": "b@x.io"` to the JSON.

**`test_rw_deactivate_failure_does_not_break_merge`** (around line 326):
- Add `email="b@x.io"` to B's add_user.
- Add `"email": "b@x.io"` to the JSON.

- [ ] **Step 2: Run endpoint tests, verify some now fail differently**

Run:
```bash
python -m pytest tests/test_link_by_url_router.py::TestLinkByUrlEndpoint -v
```
Expected: tests that send a successful merge (`test_merged_pro_...`, `test_both_pro_...`, `test_self_import_...`, `test_rw_deactivate_failure_...`) **still fail** because the router doesn't pass `claimed_email` to the merge function yet — they get 500. Tests like `test_invalid_url_returns_422` and `test_rw_lookup_miss_returns_404` pass because they short-circuit before reaching the merge call.

This intermediate state is expected — Task 3b fixes it.

(No commit at this step. The next step is Task 3b.)

### Task 3b: Pass `claimed_email` through + enrich the failure notify

- [ ] **Step 1: Update the endpoint's call to `import_subscription_by_uuid`**

In `miniapp/backend/android/link_router.py`, find the call (currently around line 156-160):

```python
            merge = await import_subscription_by_uuid(
                s,
                current_user_id=user.id,
                b_rw_short_uuid=short_uuid,
            )
```

Replace with:

```python
            merge = await import_subscription_by_uuid(
                s,
                current_user_id=user.id,
                b_rw_short_uuid=short_uuid,
                claimed_email=payload.email,
            )
```

- [ ] **Step 2: Enrich the LookupNotFound notify_log message**

Still in `miniapp/backend/android/link_router.py`, find the existing `LookupNotFound` branch's `pending_notify` (currently around line 163-166):

```python
            pending_notify = (
                f"❌ <b>Android sub-URL import: rw_not_found</b>\n"
                f"user=<code>{user.id}</code> "
                f"short_uuid=<code>{esc(short_uuid)}</code>"
            )
```

Replace with:

```python
            pending_notify = (
                f"❌ <b>Android sub-URL import: rw_not_found</b>\n"
                f"user=<code>{user.id}</code> "
                f"short_uuid=<code>{esc(short_uuid)}</code>\n"
                f"claimed_email=<code>{esc(payload.email)}</code>"
            )
```

- [ ] **Step 3: Run all router endpoint tests, expect green**

Run:
```bash
python -m pytest tests/test_link_by_url_router.py -v
```
Expected: 21 passed (11 parser + 10 updated endpoint tests). New tests come in Task 3c.

- [ ] **Step 4: Run the merge suite — no regressions**

Run:
```bash
python -m pytest tests/test_android_link_merge.py -q
```
Expected: 52 passed.

- [ ] **Step 5: Commit**

```bash
git add miniapp/backend/android/link_router.py tests/test_link_by_url_router.py
git commit -m "feat(miniapp): forward claimed_email to import_subscription_by_uuid

Router now passes payload.email through to the merge function. The
rw_not_found notify_log message includes claimed_email so admins can
distinguish 'URL not in RW' from 'URL found, email wrong' in their
alert stream (the wire response stays uniform 404 by design).

Tests updated to send 'email' in the request body and to seed B's RW
email accordingly.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 3c: Add 4 new endpoint tests

- [ ] **Step 1: Write the 4 new failing tests**

Append to `TestLinkByUrlEndpoint` in `tests/test_link_by_url_router.py` (after the last existing test):

```python
    def test_missing_email_returns_422(
        self, link_by_url_client,
    ):
        """Pydantic rejects body without 'email' field."""
        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL},
        )
        assert resp.status_code == 422

    def test_malformed_email_returns_422(
        self, link_by_url_client,
    ):
        """Pydantic EmailStr rejects 'not-an-email'."""
        resp = link_by_url_client.post(
            "/api/android/link/by_url",
            json={"url": URL, "email": "not-an-email"},
        )
        assert resp.status_code == 422

    def test_email_mismatch_returns_404_rw_not_found(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        """RW has B with email=b@x.io; client claims other@x.io.
        Response is identical to test_rw_lookup_miss_returns_404 — by
        design (no oracle).
        """
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=SHORT,
                                email="b@x.io",
                                status="active",
                                data_limit=10 * 1024 ** 3)
        self._seed_a(with_app_db)

        resp = link_by_url_client.post(
            "/api/android/link/by_url",
            json={"url": URL, "email": "other@x.io"},
        )
        assert resp.status_code == 404
        assert resp.json() == {"detail": {"code": "rw_not_found"}}

    def test_email_mismatch_notify_carries_claimed_email(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        """Admin notify_log on rw_not_found carries the claimed_email so
        ops can grep for patterns. (logger.info inside the merge function
        carries the actual rw_email too, but we don't inspect logs here.)
        """
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=SHORT,
                                email="b@x.io",
                                status="active",
                                data_limit=10 * 1024 ** 3)
        self._seed_a(with_app_db)

        link_by_url_client.post(
            "/api/android/link/by_url",
            json={"url": URL, "email": "other@x.io"},
        )
        assert any(
            "rw_not_found" in m and "other@x.io" in m
            for m in link_by_url_app.state.notify_calls
        )
```

- [ ] **Step 2: Run new tests, expect green**

Run:
```bash
python -m pytest tests/test_link_by_url_router.py::TestLinkByUrlEndpoint -v
```
Expected: 14 passed (10 updated + 4 new).

- [ ] **Step 3: Run the full file (parser tests + endpoint tests)**

Run:
```bash
python -m pytest tests/test_link_by_url_router.py -v
```
Expected: 25 passed (11 parser + 14 endpoint).

- [ ] **Step 4: Commit**

```bash
git add tests/test_link_by_url_router.py
git commit -m "test(android-link): cover email-confirmation router branches

- 422 for missing email
- 422 for malformed email
- 404 rw_not_found for email mismatch (identical to URL-miss by design)
- notify_log on rw_not_found carries claimed_email for admin triage

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Final verification

**Files:** none modified.

- [ ] **Step 1: Run the top-level tests**

Run:
```bash
python -m pytest tests/ -q
```
Expected: 77 passed (52 merge + 25 router).

- [ ] **Step 2: Run the common_db tests**

Run:
```bash
python -m pytest packages/common_db/tests/ -q
```
Expected: 186 passed, 1 skipped (no regressions from earlier baseline).

- [ ] **Step 3: Smoke-import the modified production modules**

Run:
```bash
python -c "from miniapp.backend.android.schemas_data import LinkByUrlRequest; from app.handlers.android_link_merge import import_subscription_by_uuid; from miniapp.backend.android.link_router import link_by_url; import inspect; sig = inspect.signature(import_subscription_by_uuid); assert 'claimed_email' in sig.parameters; print('ok')"
```
Expected: `ok`.

- [ ] **Step 4: Eyeball the diff against `develop`'s starting point for this feature**

Run:
```bash
git log --oneline db4ae64..HEAD
```
Expected: 4-5 commits (Task 1, Task 2a, Task 2b, Task 3a+3b combined, Task 3c). All with `feat(...)`, `refactor(...)`, or `test(...)` prefixes.

No code changes during verification — if anything is broken, return to the failing task.

---

## Self-Review

### Spec coverage check

For each section/requirement in `docs/superpowers/specs/2026-05-21-android-link-by-url-email-design.md`:

- "Request schema — `LinkByUrlRequest.email: EmailStr`" → Task 1.
- "Merge function — new `claimed_email` kwarg" → Task 2a.
- "Email compare branch (case- and whitespace-insensitive, rejects RW-empty, raises `LookupNotFound`)" → Task 2b Step 3.
- "Email check runs BEFORE self-import short-circuit" → Task 2b Step 3 (the new block is placed between `b_info is None` check and `if a.vless_uuid is not None and a.vless_uuid == b_rw_uuid:` short-circuit). Verified by `test_self_import_with_wrong_email_raises_lookup_not_found`.
- "Router passes `claimed_email=payload.email`" → Task 3b Step 1.
- "Notify_log on rw_not_found carries `claimed_email`" → Task 3b Step 2. Verified by `test_email_mismatch_notify_carries_claimed_email`.
- "Error matrix (wire-visible)": 422 invalid_url → existing tests; 422 malformed email → new test 3c; 404 rw_not_found for URL-miss → existing test; 404 rw_not_found for email mismatch → new test 3c; 404 rw_not_found for RW-empty email → covered by `test_rw_email_missing_raises_lookup_not_found` in Task 2b.
- "Test list": all 14 unit-merge tests + all 14 router tests accounted for above.

### Placeholder scan

No "TBD", "TODO", or vague directives anywhere. Every code step shows full code; every command is concrete; every expected output is stated. The list of "per-test edits" in Task 2a and Task 3a names each test by current line number AND test name — engineers can locate them either way if line numbers shift.

### Type consistency

- `claimed_email: str` everywhere it's a function/method parameter (production code, test helpers, test calls).
- `email: EmailStr` only in the Pydantic schema. When FastAPI parses the request, `payload.email` is the `str`-coercible `EmailStr` value — using it as a plain string downstream is correct (Pydantic's `EmailStr` subclasses `str`).
- `LookupNotFound` is the existing exception type; we do NOT subclass or add fields. The router's existing `except LookupNotFound:` handler catches both reasons (URL miss and email mismatch) uniformly — verified by `test_rw_lookup_miss_returns_404` and `test_email_mismatch_returns_404_rw_not_found` producing identical wire responses.
- `fake_remnawave.add_user(... email=...)` accepts `str | None` (verified at `tests/conftest.py:62`). All test changes use either `email="b@x.io"` (str) or `email=None`, both supported.

### Known limitations acknowledged

- Like the parent feature, running `pytest tests/ packages/common_db/tests/` jointly still hits the `tests` namespace collision documented in earlier specs. Task 4 runs them separately, same as the by_url plan.
- `EmailStr` strictness: Pydantic's `email-validator` package treats some technically-valid RFC 5322 forms (e.g. quoted local-parts) as invalid. We accept this — if a real user has such an email in Remnawave, they can request manual support. Not in scope for this feature.

---

## Out of scope (reminder)

- Notifying user B (the URL's original owner) of an import attempt.
- Email confirmation for the Telegram-link flow (`POST /api/android/link/start`).
- Replacing email with a stronger factor (HMAC, OTP).
- Rate-limit tightening (`3/minute` already applies).
- Discriminating mismatch vs URL-miss on the wire (logged internally, kept opaque externally).
