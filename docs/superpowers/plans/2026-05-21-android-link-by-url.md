# Android Link by URL — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `POST /api/android/link/by_url` that imports a Remnawave subscription URL into the authenticated Android user's account, applying the same PRO/FREE merge matrix used in the tg-link flow, with the wrinkle that the source side (B) may not exist in our DB at all — only in Remnawave.

**Architecture:** Reuse `_classify` and `_decide` from `app/handlers/android_link_merge.py`. Add a new public coroutine `import_subscription_by_uuid` in the same module that operates on a single DB row (A = current user) and a virtual B-side resolved entirely via Remnawave by `short_uuid`. Add a new endpoint in `miniapp/backend/android/link_router.py` that parses the URL, dispatches the merge, performs a best-effort RW deactivate of the loser uuid (if any), and emits a `notify_log` for every outcome.

**Tech Stack:** FastAPI + Pydantic v2, SQLAlchemy 2.0 async + aiosqlite for tests, slowapi for rate-limiting, the shared `remnawave_client` SDK, pytest with the existing in-memory `with_app_db` fixture.

---

## File Structure

**New files:**
- `tests/test_link_by_url_router.py` — router-level integration tests using FastAPI `TestClient`.

**Modified files:**
- `app/api/remnawave/api.py` — add a one-line shim re-exporting `get_user_by_short_uuid_raw` from the SDK (the miniapp shim already has it; the bot-side does not).
- `app/handlers/android_link_merge.py` — add `LookupNotFound`, `_lookup_a_side_rw`, `import_subscription_by_uuid`.
- `miniapp/backend/android/schemas_data.py` — add `LinkByUrlRequest`, `LinkByUrlResponse`.
- `miniapp/backend/android/link_router.py` — add `POST /by_url` endpoint + `_parse_short_uuid` URL parser.
- `tests/conftest.py` — extend `FakeRemnawave` with `short_uuid` indexing + `get_user_by_short_uuid_raw`, and monkeypatch it onto both the bot-side and miniapp-side `rem` shims.
- `tests/test_android_link_merge.py` — append `TestImportSubscriptionByUuid` class with 9 cases.

Each unit has one clear responsibility:
- `android_link_merge.py` keeps owning the matrix and the RW lookups.
- `link_router.py` owns URL parsing, HTTP shape, rate-limit, and notify_log.
- `conftest.py` owns the `FakeRemnawave` test double.
- Test files mirror their production counterparts 1:1.

---

## Task 1: Add `get_user_by_short_uuid_raw` shim to bot-side rem module

**Files:**
- Modify: `app/api/remnawave/api.py` (append after `get_user_from_uuid` definition)
- Test: `tests/test_android_link_merge.py` (existing — we'll verify via downstream tests in Task 5)

The bot-side `rem` shim lacks the function we need; the miniapp shim has it (`miniapp/backend/remnawave_client.py:88`). Mirror that shim.

- [ ] **Step 1: Verify the function is missing**

Run:
```bash
grep -n "get_user_by_short_uuid_raw" C:/Users/Lynx/PycharmProjects/xray-vpn-bot/app/api/remnawave/api.py
```
Expected: no output (function missing).

- [ ] **Step 2: Add the shim**

Edit `app/api/remnawave/api.py` — append immediately after the `get_user_from_uuid` function (around line 44):

```python
async def get_user_by_short_uuid_raw(short_uuid: str) -> dict | None:
    """Return the raw Remnawave SDK DTO for the user owning `short_uuid`.

    Mirrors `miniapp/backend/remnawave_client.py:get_user_by_short_uuid_raw`.
    The Android subscription-URL import flow calls this from
    `app.handlers.android_link_merge.import_subscription_by_uuid`.
    """
    return await _client().get_user_by_short_uuid_raw(short_uuid)
```

- [ ] **Step 3: Verify the import compiles**

Run:
```bash
python -c "import app.api.remnawave.api as rem; print(rem.get_user_by_short_uuid_raw)"
```
Expected: `<function get_user_by_short_uuid_raw at 0x...>` — no ImportError.

- [ ] **Step 4: Commit**

```bash
git add app/api/remnawave/api.py
git commit -m "feat(rem): add get_user_by_short_uuid_raw shim on bot-side

Mirrors the existing miniapp shim. Needed by the new
import_subscription_by_uuid flow.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Extend `FakeRemnawave` with `short_uuid` index

**Files:**
- Modify: `tests/conftest.py:41-108` (the `FakeRemnawave` class and its fixture).

We need the test double to support B-side lookups by short_uuid and to register itself on both the bot-side and miniapp-side `rem` modules.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_android_link_merge.py` at the bottom of the file:

```python
class TestFakeRemnawaveShortUuid:
    """Sanity-check the FakeRemnawave short_uuid extension before the
    real import_subscription_by_uuid tests rely on it."""

    def test_short_uuid_lookup_returns_full_record(self, fake_remnawave):
        fake_remnawave.add_user(
            uuid="b-uuid", short_uuid="sN_xxxxxxxxxxxx",
            status="active", data_limit=None, email="b@x.io",
        )
        import app.api.remnawave.api as rem
        rec = _asyncio.run(rem.get_user_by_short_uuid_raw("sN_xxxxxxxxxxxx"))
        assert rec is not None
        assert rec["uuid"] == "b-uuid"
        assert rec["status"] == "active"

    def test_short_uuid_lookup_returns_none_for_unknown(self, fake_remnawave):
        import app.api.remnawave.api as rem
        rec = _asyncio.run(rem.get_user_by_short_uuid_raw("missing"))
        assert rec is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest tests/test_android_link_merge.py::TestFakeRemnawaveShortUuid -v
```
Expected: FAIL with `TypeError: add_user() got an unexpected keyword argument 'short_uuid'` or `AttributeError: ... get_user_by_short_uuid_raw`.

- [ ] **Step 3: Extend `FakeRemnawave`**

Edit `tests/conftest.py` — modify the `FakeRemnawave` class:

In `__init__` (line 51), add the `by_short_uuid` map:

```python
    def __init__(self):
        self.by_uuid: dict[str, dict] = {}
        self.by_email: dict[str, str] = {}
        self.by_username: dict[str, str] = {}
        self.by_short_uuid: dict[str, str] = {}
        self.disabled_calls: list[str] = []
        self.update_should_raise: Exception | None = None
```

In `add_user` (line 58), accept `short_uuid` and store it on the record + reverse map:

```python
    def add_user(self, *, uuid: str, status: str = "active",
                 data_limit=None, email: str | None = None,
                 username: str | None = None,
                 subscription_url: str | None = None,
                 short_uuid: str | None = None) -> None:
        rec = {
            "uuid": uuid,
            "status": status,
            "data_limit": data_limit,
            "email": email,
            "username": username,
            "subscription_url": subscription_url,
            "short_uuid": short_uuid,
        }
        self.by_uuid[uuid] = rec
        if email:
            self.by_email[email] = uuid
        if username:
            self.by_username[username] = uuid
        if short_uuid:
            self.by_short_uuid[short_uuid] = uuid
```

Add a new method after `get_user_from_uuid` (line 85):

```python
    async def get_user_by_short_uuid_raw(self, short_uuid: str):
        uuid = self.by_short_uuid.get(short_uuid)
        return self.by_uuid.get(uuid) if uuid else None
```

In the `fake_remnawave` fixture (line 99), add monkeypatch for the new function on both the bot-side and the miniapp-side modules:

```python
@pytest.fixture
def fake_remnawave(monkeypatch) -> FakeRemnawave:
    fake = FakeRemnawave()
    import app.api.remnawave.api as rem
    monkeypatch.setattr(rem, "get_user_from_email", fake.get_user_from_email)
    monkeypatch.setattr(rem, "get_user_from_username", fake.get_user_from_username)
    monkeypatch.setattr(rem, "update_user", fake.update_user)
    # get_user_from_uuid не существует в api shim — добавляем атрибут.
    monkeypatch.setattr(rem, "get_user_from_uuid", fake.get_user_from_uuid,
                        raising=False)
    monkeypatch.setattr(rem, "get_user_by_short_uuid_raw",
                        fake.get_user_by_short_uuid_raw, raising=False)
    # Mirror onto the miniapp shim so router tests that import
    # `..remnawave_client as rem` see the same fake.
    try:
        import miniapp.backend.remnawave_client as mrem
        monkeypatch.setattr(mrem, "get_user_from_email",
                            fake.get_user_from_email)
        monkeypatch.setattr(mrem, "get_user_from_username",
                            fake.get_user_from_username)
        monkeypatch.setattr(mrem, "get_user_from_uuid",
                            fake.get_user_from_uuid, raising=False)
        monkeypatch.setattr(mrem, "get_user_by_short_uuid_raw",
                            fake.get_user_by_short_uuid_raw, raising=False)
        monkeypatch.setattr(mrem, "update_user", fake.update_user)
    except ImportError:
        pass
    return fake
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
python -m pytest tests/test_android_link_merge.py::TestFakeRemnawaveShortUuid -v
```
Expected: 2 passed.

- [ ] **Step 5: Run the full suite to confirm nothing else regressed**

Run:
```bash
python -m pytest tests/test_android_link_merge.py -v
```
Expected: all tests pass (original 30 + the new 2 = 32).

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_android_link_merge.py
git commit -m "test(android-link): extend FakeRemnawave with short_uuid index

Adds by_short_uuid map and get_user_by_short_uuid_raw method.
Fixture mirrors monkeypatches onto miniapp.backend.remnawave_client
so router-level tests can reuse the same fake.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Add `LookupNotFound` exception and `_lookup_a_side_rw` helper

**Files:**
- Modify: `app/handlers/android_link_merge.py` (append below `_none()`).
- Test: `tests/test_android_link_merge.py` (append before the existing `TestFakeRemnawaveShortUuid` block).

These are the building blocks needed by `import_subscription_by_uuid` (Task 4). Keeping them as their own task makes the RED phase of Task 4 isolated.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_android_link_merge.py` immediately after the existing `TestLookupRw` class (around line 75):

```python
from app.handlers.android_link_merge import (
    LookupNotFound,
    _lookup_a_side_rw,
)


class TestLookupASideRw:
    """A-side-only lookup helper used by import_subscription_by_uuid."""

    def test_returns_none_when_both_identifiers_missing(self, fake_remnawave):
        result = asyncio.run(_lookup_a_side_rw(vless_uuid=None, email=None))
        assert result is None

    def test_finds_by_vless_uuid_first(self, fake_remnawave):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        result = asyncio.run(_lookup_a_side_rw(
            vless_uuid="a-uuid", email="a@x.io",
        ))
        assert result is not None
        assert result["uuid"] == "a-uuid"

    def test_falls_back_to_email_when_uuid_missing(self, fake_remnawave):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        result = asyncio.run(_lookup_a_side_rw(
            vless_uuid=None, email="a@x.io",
        ))
        assert result is not None
        assert result["uuid"] == "a-uuid"

    def test_swallows_exceptions_returns_none(self, fake_remnawave, monkeypatch):
        async def boom(*a, **kw):
            raise RuntimeError("network down")
        import app.api.remnawave.api as rem
        monkeypatch.setattr(rem, "get_user_from_uuid", boom)
        result = asyncio.run(_lookup_a_side_rw(
            vless_uuid="a-uuid", email=None,
        ))
        assert result is None


class TestLookupNotFound:
    def test_is_an_exception(self):
        assert issubclass(LookupNotFound, Exception)

    def test_carries_short_uuid_detail(self):
        exc = LookupNotFound("missing-short")
        assert "missing-short" in str(exc)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_android_link_merge.py::TestLookupASideRw tests/test_android_link_merge.py::TestLookupNotFound -v
```
Expected: ImportError on `LookupNotFound` and `_lookup_a_side_rw`.

- [ ] **Step 3: Add the implementations**

Edit `app/handlers/android_link_merge.py`. Append immediately after the `_none()` coroutine (after line 71):

```python
class LookupNotFound(Exception):
    """Raised when get_user_by_short_uuid_raw returns None — the imported
    subscription URL pointed at a non-existent Remnawave user. The router
    maps this to HTTP 404 with code=rw_not_found.
    """

    def __init__(self, short_uuid: str):
        super().__init__(f"rw_not_found: {short_uuid}")
        self.short_uuid = short_uuid


async def _lookup_a_side_rw(
    *,
    vless_uuid: str | None,
    email: str | None,
) -> dict | None:
    """Look up the current user (A-side) in Remnawave.

    Tries vless_uuid first (authoritative when set), falls back to email.
    Returns the Remnawave dict or None on miss/error. Mirrors the A-side
    branch of `_lookup_rw` but without the TG-side concurrent fetch — the
    by_url flow already has B-side loaded via short_uuid.
    """
    import app.api.remnawave.api as rem

    if vless_uuid:
        try:
            info = await rem.get_user_from_uuid(vless_uuid)
        except Exception as exc:
            logger.warning("Remnawave A-side uuid lookup failed: %s", exc)
            info = None
        if info:
            return info
    if email:
        try:
            return await rem.get_user_from_email(email)
        except Exception as exc:
            logger.warning("Remnawave A-side email lookup failed: %s", exc)
            return None
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_android_link_merge.py::TestLookupASideRw tests/test_android_link_merge.py::TestLookupNotFound -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add app/handlers/android_link_merge.py tests/test_android_link_merge.py
git commit -m "feat(android-link): add LookupNotFound + _lookup_a_side_rw helper

Building blocks for import_subscription_by_uuid. _lookup_a_side_rw is
the single-side analogue of _lookup_rw without the concurrent B-side
fetch — by_url already has B loaded via short_uuid.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Implement `import_subscription_by_uuid`

**Files:**
- Modify: `app/handlers/android_link_merge.py` (append below `_lookup_a_side_rw`).
- Test: `tests/test_android_link_merge.py` (append `TestImportSubscriptionByUuid`).

The core function. Single DB write (`A.vless_uuid = chosen_uuid`); caller commits.

- [ ] **Step 1: Write all 9 failing tests**

Append to `tests/test_android_link_merge.py` at the end of the file (after `TestFakeRemnawaveShortUuid`):

```python
from app.handlers.android_link_merge import import_subscription_by_uuid


class TestImportSubscriptionByUuid:
    """End-to-end matrix coverage for the by_url import flow."""

    SHORT = "sN_RHMk6BGv-RJ8g"

    def _run(self, session_factory, *, current_user_id, short_uuid):
        async def go():
            async with session_factory() as s:
                result = await import_subscription_by_uuid(
                    s,
                    current_user_id=current_user_id,
                    b_rw_short_uuid=short_uuid,
                )
                await s.commit()
                survivor = await s.get(User, current_user_id)
                return result, survivor.vless_uuid

        return _asyncio.run(go())

    def test_pro_a_free_b_keeps_a_disables_b(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                status="active",
                                data_limit=10 * 1024 ** 3)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid"))
                await s.commit()
        _asyncio.run(seed())

        result, vless = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
        )
        assert result["result"] == "merged_pro"
        assert result["a_tier"] == "pro"
        assert result["b_tier"] == "free"
        assert result["chosen_uuid"] == "a-uuid"
        assert result["loser_rw_uuid"] == "b-uuid"
        assert vless == "a-uuid"

    def test_free_a_pro_b_keeps_b_disables_a(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active",
                                data_limit=5 * 1024 ** 3)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                status="active", data_limit=None)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid"))
                await s.commit()
        _asyncio.run(seed())

        result, vless = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
        )
        assert result["result"] == "merged_pro"
        assert result["a_tier"] == "free"
        assert result["b_tier"] == "pro"
        assert result["chosen_uuid"] == "b-uuid"
        assert result["loser_rw_uuid"] == "a-uuid"
        assert vless == "b-uuid"

    def test_free_a_free_b_keeps_b_disables_a(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active",
                                data_limit=5 * 1024 ** 3)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                status="active",
                                data_limit=10 * 1024 ** 3)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid"))
                await s.commit()
        _asyncio.run(seed())

        result, vless = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
        )
        assert result["result"] == "merged_free"
        assert result["chosen_uuid"] == "b-uuid"
        assert result["loser_rw_uuid"] == "a-uuid"
        assert vless == "b-uuid"

    def test_pro_a_pro_b_raises_merge_blocked_no_writes(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                status="active", data_limit=None)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid"))
                await s.commit()
        _asyncio.run(seed())

        async def go():
            async with session_factory() as s:
                with pytest.raises(MergeBlocked):
                    await import_subscription_by_uuid(
                        s, current_user_id=100, b_rw_short_uuid=self.SHORT,
                    )
                # Verify nothing changed.
                survivor = await s.get(User, 100)
                return survivor.vless_uuid

        vless = _asyncio.run(go())
        assert vless == "a-uuid"
        assert fake_remnawave.disabled_calls == []

    def test_a_none_b_free_simple_takeover(
        self, session_factory, fake_remnawave,
    ):
        # A has no email and no vless_uuid → tier "none".
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                status="active",
                                data_limit=10 * 1024 ** 3)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, tg_id=55))
                await s.commit()
        _asyncio.run(seed())

        result, vless = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
        )
        assert result["result"] == "ok"
        assert result["a_tier"] == "none"
        assert result["b_tier"] == "free"
        assert result["chosen_uuid"] == "b-uuid"
        assert result["loser_rw_uuid"] is None
        assert vless == "b-uuid"

    def test_a_none_b_pro_simple_takeover(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                status="active", data_limit=None)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, tg_id=55))
                await s.commit()
        _asyncio.run(seed())

        result, vless = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
        )
        assert result["result"] == "ok"
        assert result["a_tier"] == "none"
        assert result["b_tier"] == "pro"
        assert result["chosen_uuid"] == "b-uuid"
        assert result["loser_rw_uuid"] is None
        assert vless == "b-uuid"

    def test_self_import_short_circuits(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", short_uuid=self.SHORT,
                                email="a@x.io",
                                status="active", data_limit=None)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid"))
                await s.commit()
        _asyncio.run(seed())

        result, vless = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
        )
        assert result["result"] == "already_owned"
        assert result["chosen_uuid"] == "a-uuid"
        assert result["loser_rw_uuid"] is None
        # A.vless_uuid unchanged.
        assert vless == "a-uuid"
        # No disable calls executed by the function itself.
        assert fake_remnawave.disabled_calls == []

    def test_b_not_found_raises_lookup_not_found(
        self, session_factory, fake_remnawave,
    ):
        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid"))
                await s.commit()
        _asyncio.run(seed())

        async def go():
            async with session_factory() as s:
                with pytest.raises(LookupNotFound):
                    await import_subscription_by_uuid(
                        s, current_user_id=100, b_rw_short_uuid="nope",
                    )
                survivor = await s.get(User, 100)
                return survivor.vless_uuid

        vless = _asyncio.run(go())
        assert vless == "a-uuid"

    def test_a_email_fallback_when_vless_uuid_missing(
        self, session_factory, fake_remnawave,
    ):
        """A.vless_uuid is None but A.email resolves to PRO in RW.

        Verifies the A-side email-fallback branch of _lookup_a_side_rw.
        Expected outcome: PRO A + FREE B → merged_pro, chosen_uuid=A.uuid.
        """
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                status="active",
                                data_limit=10 * 1024 ** 3)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io"))  # no vless_uuid
                await s.commit()
        _asyncio.run(seed())

        result, vless = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
        )
        assert result["result"] == "merged_pro"
        assert result["chosen_uuid"] == "a-uuid"
        assert result["loser_rw_uuid"] == "b-uuid"
        assert vless == "a-uuid"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_android_link_merge.py::TestImportSubscriptionByUuid -v
```
Expected: 9 errors with `ImportError: cannot import name 'import_subscription_by_uuid'`.

- [ ] **Step 3: Implement `import_subscription_by_uuid`**

Edit `app/handlers/android_link_merge.py`. Append at the very end of the file (after `merge_android_and_tg`):

```python
async def import_subscription_by_uuid(
    session,
    *,
    current_user_id: int,
    b_rw_short_uuid: str,
) -> dict[str, Any]:
    """Import a Remnawave subscription URL into the current user's account.

    A = current user (must exist in DB).
    B = subscription owner identified by Remnawave short_uuid (may not exist
        in our DB — only RW is consulted for B).

    Reuses the PRO/FREE matrix from `_decide` by mapping
    A → "android-side" and B → "tg-side". `survivor_id`/`loser_id` outputs
    of `_decide` are ignored here (only one DB row exists).

    Returns:
      {
        "result": "merged_pro" | "merged_free" | "ok" | "already_owned",
        "a_tier": "pro" | "free" | "none",
        "b_tier": "pro" | "free",
        "a_rw_uuid": str | None,
        "b_rw_uuid": str,
        "chosen_uuid": str,
        "loser_rw_uuid": str | None,
      }

    Raises:
      MergeBlocked    — both A and B are PRO. No writes performed.
      LookupNotFound  — RW returned no user for the short_uuid.

    The caller commits the session. RW-side deactivation of the loser
    uuid (if any) is the caller's responsibility too — this function
    does not touch the Remnawave API beyond read lookups.
    """
    import app.api.remnawave.api as rem
    from common_db.models import User

    a = await session.get(User, current_user_id)
    if a is None:
        raise RuntimeError(f"a_user_not_found: {current_user_id}")

    b_info = await rem.get_user_by_short_uuid_raw(b_rw_short_uuid)
    if b_info is None:
        raise LookupNotFound(b_rw_short_uuid)

    b_rw_uuid = b_info["uuid"]

    # Self-import: pasted own URL → no-op.
    if a.vless_uuid is not None and a.vless_uuid == b_rw_uuid:
        tier = _classify(b_info)
        return {
            "result": "already_owned",
            "a_tier": tier,
            "b_tier": tier,
            "a_rw_uuid": b_rw_uuid,
            "b_rw_uuid": b_rw_uuid,
            "chosen_uuid": b_rw_uuid,
            "loser_rw_uuid": None,
        }

    a_info = await _lookup_a_side_rw(
        vless_uuid=a.vless_uuid, email=a.email,
    )
    a_tier = _classify(a_info)
    b_tier = _classify(b_info)
    a_rw_uuid = (a_info or {}).get("uuid")

    # Map A → android-side, B → tg-side. survivor/loser ids are
    # meaningless (only one DB row); we use the caller's id for both
    # slots so _decide doesn't see None and stays consistent.
    _survivor, _loser, chosen_uuid, result_code = _decide(
        a_tier=a_tier, t_tier=b_tier,
        a_rw_uuid=a_rw_uuid, t_rw_uuid=b_rw_uuid,
        android_id=current_user_id, tg_user_id=current_user_id,
    )

    if chosen_uuid == a_rw_uuid:
        loser_rw_uuid = b_rw_uuid
    elif chosen_uuid == b_rw_uuid:
        loser_rw_uuid = a_rw_uuid  # may be None when A had no RW user
    else:
        loser_rw_uuid = None  # defensive — chosen should always match one

    a.vless_uuid = chosen_uuid
    await session.flush()

    logger.info(
        "import_subscription_by_uuid: user=%s a_tier=%s b_tier=%s "
        "chosen=%s loser=%s code=%s",
        current_user_id, a_tier, b_tier, chosen_uuid, loser_rw_uuid,
        result_code,
    )

    return {
        "result": result_code,
        "a_tier": a_tier,
        "b_tier": b_tier,
        "a_rw_uuid": a_rw_uuid,
        "b_rw_uuid": b_rw_uuid,
        "chosen_uuid": chosen_uuid,
        "loser_rw_uuid": loser_rw_uuid,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_android_link_merge.py::TestImportSubscriptionByUuid -v
```
Expected: 9 passed.

- [ ] **Step 5: Run full merge test suite — no regressions**

Run:
```bash
python -m pytest tests/test_android_link_merge.py -v
```
Expected: all green (32 original + 6 from Task 3 + 9 new = 47, give or take a couple from Task 2's sanity tests).

- [ ] **Step 6: Commit**

```bash
git add app/handlers/android_link_merge.py tests/test_android_link_merge.py
git commit -m "feat(android-link): import_subscription_by_uuid

Implements POST /api/android/link/by_url backbone. Reuses the
PRO/FREE matrix from _decide by mapping A→android-side, B→tg-side.
B may be virtual — RW is the only source of truth. Single DB write
(A.vless_uuid = chosen); caller commits and handles RW deactivation.

Self-import short-circuits to result=already_owned with no writes.
RW miss raises LookupNotFound for the router to translate to 404.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Add `LinkByUrlRequest` / `LinkByUrlResponse` schemas

**Files:**
- Modify: `miniapp/backend/android/schemas_data.py` (append at end).
- Test: covered indirectly by the router tests in Task 7. No standalone schema tests — Pydantic validation is stdlib-equivalent.

- [ ] **Step 1: Add schemas**

Edit `miniapp/backend/android/schemas_data.py`. Append after `LinkStartResponse`:

```python
class LinkByUrlRequest(BaseModel):
    url: str  # Validated by _parse_short_uuid in the router; plain str
              # avoids Pydantic HttpUrl's strict percent-encoding edge
              # cases (some clients send raw `:` in path).


class LinkByUrlResponse(BaseModel):
    result: str    # merged_pro | merged_free | ok | already_owned | both_pro_support_needed
    a_tier: str    # pro | free | none
    b_tier: str    # pro | free
```

- [ ] **Step 2: Verify import**

Run:
```bash
python -c "from miniapp.backend.android.schemas_data import LinkByUrlRequest, LinkByUrlResponse; print(LinkByUrlRequest.model_fields, LinkByUrlResponse.model_fields)"
```
Expected: prints two model-field dicts; no ImportError.

- [ ] **Step 3: Commit**

```bash
git add miniapp/backend/android/schemas_data.py
git commit -m "feat(miniapp): add LinkByUrlRequest/Response schemas

Plain str for url instead of HttpUrl — Pydantic v2's HttpUrl rejects
some valid subscription URLs with raw `:` in path. The router does
strict validation via _parse_short_uuid.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Implement `_parse_short_uuid` URL parser

**Files:**
- Modify: `miniapp/backend/android/link_router.py` (add module-level helper).
- Test: `tests/test_link_by_url_router.py` (NEW — start with parser tests).

We test the parser as a pure function before wiring it into the route.

- [ ] **Step 1: Create the new test file with parser tests**

Create `tests/test_link_by_url_router.py`:

```python
"""Router-level tests for POST /api/android/link/by_url.

Uses FastAPI TestClient. Builds a minimal app importing only the
link_router, overrides deps.require_verified_email, monkeypatches
notify_log and Remnawave shims, and redirects async_session via the
existing with_app_db fixture.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from miniapp.backend.android.link_router import _parse_short_uuid


class TestParseShortUuid:
    """Pure URL → short_uuid parser, no FastAPI involvement."""

    GOOD_URL = "https://sub.domain.com/sN_RHMk6BGv-RJ8g"
    GOOD_SHORT = "sN_RHMk6BGv-RJ8g"

    def test_valid_https_returns_short_uuid(self):
        assert _parse_short_uuid(self.GOOD_URL) == self.GOOD_SHORT

    def test_query_string_is_ignored(self):
        assert _parse_short_uuid(self.GOOD_URL + "?ref=foo") == self.GOOD_SHORT

    def test_fragment_is_ignored(self):
        assert _parse_short_uuid(self.GOOD_URL + "#anchor") == self.GOOD_SHORT

    def test_trailing_slash_is_accepted(self):
        assert _parse_short_uuid(self.GOOD_URL + "/") == self.GOOD_SHORT

    def test_http_scheme_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _parse_short_uuid(self.GOOD_URL.replace("https://", "http://"))
        assert exc.value.status_code == 422
        assert exc.value.detail == {"code": "invalid_url"}

    def test_wrong_host_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _parse_short_uuid("https://attacker.example.com/sN_xxxxxxxxxxxx")
        assert exc.value.status_code == 422

    def test_multi_segment_path_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _parse_short_uuid(
                "https://sub.domain.com/api/sN_xxxxxxxxxxxx"
            )
        assert exc.value.status_code == 422

    def test_empty_path_rejected(self):
        with pytest.raises(HTTPException):
            _parse_short_uuid("https://sub.domain.com/")

    def test_too_short_path_rejected(self):
        # Less than 8 chars fails the regex.
        with pytest.raises(HTTPException):
            _parse_short_uuid("https://sub.domain.com/short")

    def test_invalid_characters_rejected(self):
        with pytest.raises(HTTPException):
            _parse_short_uuid(
                "https://sub.domain.com/has spaces here!"
            )

    def test_malformed_url_rejected(self):
        with pytest.raises(HTTPException):
            _parse_short_uuid("not-a-url-at-all")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_link_by_url_router.py::TestParseShortUuid -v
```
Expected: ImportError on `_parse_short_uuid`.

- [ ] **Step 3: Implement `_parse_short_uuid`**

Edit `miniapp/backend/android/link_router.py`. Add imports at the top (after the existing `from . import ...` line):

```python
import os
import re
from urllib.parse import urlparse
```

Add the module-level constants and helper after `_LINK_CODE_TTL_SECONDS` (around line 30):

```python
_SUBSCRIPTION_HOST = os.environ.get(
    "SUBSCRIPTION_HOST", "sub.domain.com",
)
_SHORT_UUID_RE = re.compile(r"^[A-Za-z0-9_-]{8,32}$")


def _parse_short_uuid(url: str) -> str:
    """Extract the short_uuid from a subscription URL.

    Strict: https only, exact host match against $SUBSCRIPTION_HOST
    (default ``sub.domain.com``), single path segment matching
    ``[A-Za-z0-9_-]{8,32}``. Query string and fragment are ignored.

    Raises ``HTTPException(422, {"code": "invalid_url"})`` on any failure.
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_url"},
        ) from exc

    if parsed.scheme != "https" or parsed.netloc != _SUBSCRIPTION_HOST:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_url"},
        )
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) != 1 or not _SHORT_UUID_RE.match(parts[0]):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_url"},
        )
    return parts[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_link_by_url_router.py::TestParseShortUuid -v
```
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add miniapp/backend/android/link_router.py tests/test_link_by_url_router.py
git commit -m "feat(miniapp): _parse_short_uuid URL parser

Strict: https only, exact host match (env-overridable), single
path segment of [A-Za-z0-9_-]{8,32}. Query/fragment ignored.
422 with code=invalid_url on any failure.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Wire `POST /api/android/link/by_url` endpoint

**Files:**
- Modify: `miniapp/backend/android/link_router.py` (append the new endpoint).
- Test: `tests/test_link_by_url_router.py` (append TestClient-based integration cases).

This is the integration glue: parse → dispatch merge → commit → best-effort RW deactivate → notify_log.

- [ ] **Step 1: Write the failing fixture + happy-path test**

Append to `tests/test_link_by_url_router.py`:

```python
import hashlib
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from common_db.models import User


@dataclass
class _FakeUser:
    id: int = 100
    email: str | None = "a@x.io"
    password_hash: str | None = "ph"
    email_verified_at: str | None = "2026-05-19T00:00:00"
    tg_id: int | None = None
    is_banned: bool = False
    language: str | None = "en"
    vless_uuid: str | None = "a-uuid"


@pytest.fixture
def link_by_url_app(with_app_db, fake_remnawave, monkeypatch):
    """Minimal FastAPI app exposing only the link_router.

    Overrides require_verified_email to return a fake user with id=100.
    Captures notify_log calls in app.state.notify_calls.
    The with_app_db fixture redirects async_session for both the
    app/handlers/android_link.py module and app/database/models. We
    additionally redirect miniapp.backend.database.session.async_session
    since the router opens its own session via that import.
    """
    import miniapp.backend.android.link_router as lr
    import miniapp.backend.android.deps as deps
    import miniapp.backend.notify_log as nl
    import miniapp.backend.database.session as mdb

    monkeypatch.setattr(mdb, "async_session", with_app_db)
    monkeypatch.setattr(lr, "async_session", with_app_db, raising=False)

    notify_calls: list[str] = []

    async def fake_notify(text, *, parse_mode="HTML"):
        notify_calls.append(text)

    monkeypatch.setattr(nl, "notify_log", fake_notify)
    monkeypatch.setattr(lr, "notify_log", fake_notify, raising=False)

    app = FastAPI()
    app.include_router(lr.router)
    app.state.notify_calls = notify_calls
    app.state.fake_user = _FakeUser()

    async def override_require_verified_email():
        return app.state.fake_user

    app.dependency_overrides[deps.require_verified_email] = (
        override_require_verified_email
    )
    # Slowapi requires app.state.limiter; reuse the router's limiter.
    app.state.limiter = lr.limiter
    return app


@pytest.fixture
def link_by_url_client(link_by_url_app):
    return TestClient(link_by_url_app)


SHORT = "sN_RHMk6BGv-RJ8g"
URL = f"https://sub.domain.com/{SHORT}"


class TestLinkByUrlEndpoint:
    def _seed_a(self, with_app_db, *, vless="a-uuid", email="a@x.io"):
        async def go():
            async with with_app_db() as s:
                s.add(User(id=100, email=email, vless_uuid=vless,
                           password_hash="ph",
                           email_verified_at="2026-05-19T00:00:00"))
                await s.commit()
        asyncio.run(go())

    def test_merged_pro_returns_200_and_disables_loser(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=SHORT,
                                status="active",
                                data_limit=10 * 1024 ** 3)
        self._seed_a(with_app_db)

        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body == {
            "result": "merged_pro",
            "a_tier": "pro",
            "b_tier": "free",
        }
        assert "b-uuid" in fake_remnawave.disabled_calls
        # A.vless_uuid unchanged (PRO A kept its uuid).
        async def fetch():
            async with with_app_db() as s:
                return (await s.get(User, 100)).vless_uuid
        assert asyncio.run(fetch()) == "a-uuid"
        # notify_log was called with the result code.
        assert any(
            "merged_pro" in m
            for m in link_by_url_app.state.notify_calls
        )

    def test_invalid_url_returns_422(
        self, link_by_url_client,
    ):
        resp = link_by_url_client.post(
            "/api/android/link/by_url",
            json={"url": "https://attacker.example.com/sN_xxxxxxxxxxxx"},
        )
        assert resp.status_code == 422
        assert resp.json() == {"detail": {"code": "invalid_url"}}

    def test_multi_segment_path_returns_422(
        self, link_by_url_client,
    ):
        resp = link_by_url_client.post(
            "/api/android/link/by_url",
            json={"url": f"https://sub.domain.com/api/{SHORT}"},
        )
        assert resp.status_code == 422

    def test_http_scheme_returns_422(
        self, link_by_url_client,
    ):
        resp = link_by_url_client.post(
            "/api/android/link/by_url",
            json={"url": URL.replace("https://", "http://")},
        )
        assert resp.status_code == 422

    def test_rw_lookup_miss_returns_404(
        self, link_by_url_client, fake_remnawave, with_app_db,
    ):
        # B short_uuid not registered → LookupNotFound.
        self._seed_a(with_app_db)
        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL},
        )
        assert resp.status_code == 404
        assert resp.json() == {"detail": {"code": "rw_not_found"}}

    def test_both_pro_returns_200_with_support_code(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=SHORT,
                                status="active", data_limit=None)
        self._seed_a(with_app_db)

        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"] == "both_pro_support_needed"
        assert body["a_tier"] == "pro"
        assert body["b_tier"] == "pro"
        # No DB change, no RW deactivate.
        assert fake_remnawave.disabled_calls == []
        async def fetch():
            async with with_app_db() as s:
                return (await s.get(User, 100)).vless_uuid
        assert asyncio.run(fetch()) == "a-uuid"
        assert any(
            "both_pro_support_needed" in m
            for m in link_by_url_app.state.notify_calls
        )

    def test_self_import_returns_already_owned(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                short_uuid=SHORT,
                                status="active", data_limit=None)
        self._seed_a(with_app_db)

        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"] == "already_owned"
        assert fake_remnawave.disabled_calls == []

    def test_email_not_verified_returns_403(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        # Toggle the fake user to unverified, then re-override.
        import miniapp.backend.android.deps as deps
        from fastapi import HTTPException, status as http_status

        async def reject():
            raise HTTPException(
                http_status.HTTP_403_FORBIDDEN, "email_not_verified",
            )

        link_by_url_app.dependency_overrides[
            deps.require_verified_email
        ] = reject

        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL},
        )
        assert resp.status_code == 403

    def test_missing_auth_dependency_returns_401(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        import miniapp.backend.android.deps as deps
        from fastapi import HTTPException, status as http_status

        async def reject():
            raise HTTPException(
                http_status.HTTP_401_UNAUTHORIZED, "missing bearer token",
            )

        link_by_url_app.dependency_overrides[
            deps.require_verified_email
        ] = reject

        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL},
        )
        assert resp.status_code == 401

    def test_rw_deactivate_failure_does_not_break_merge(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=SHORT,
                                status="active",
                                data_limit=10 * 1024 ** 3)
        fake_remnawave.update_should_raise = RuntimeError("rw down")
        self._seed_a(with_app_db)

        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL},
        )
        assert resp.status_code == 200
        assert resp.json()["result"] == "merged_pro"
        assert any(
            "Failed to disable" in m
            for m in link_by_url_app.state.notify_calls
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_link_by_url_router.py::TestLinkByUrlEndpoint -v
```
Expected: every test errors with `404 Not Found` (route doesn't exist) or `ImportError`.

- [ ] **Step 3: Implement the endpoint**

Edit `miniapp/backend/android/link_router.py`. Add imports at the top:

```python
import logging
```

(skip if `import logging` already present — it isn't currently). Also add:

```python
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: F401 — for IDE hint

from ..database.session import async_session
from ..notify_log import esc, notify_log
from ..remnawave_client import get_user_by_short_uuid_raw, update_user
from .schemas_data import LinkByUrlRequest, LinkByUrlResponse, LinkStartResponse
```

(merge with the existing `from .schemas_data import LinkStartResponse` line — replace it with the combined import above.)

Append at the end of the file, after `unlink_telegram`:

```python
@router.post("/by_url", response_model=LinkByUrlResponse)
@limiter.limit("3/minute")
async def link_by_url(
    request: Request,
    payload: LinkByUrlRequest,
    user: repo.UserRow = Depends(deps.require_verified_email),
) -> LinkByUrlResponse:
    """Import a Remnawave subscription URL into the authenticated account.

    Flow:
      1. Parse short_uuid from URL (422 on bad shape).
      2. Run import_subscription_by_uuid in a new session.
         - LookupNotFound  → 404 rw_not_found.
         - MergeBlocked    → 200 both_pro_support_needed.
         - Any other exc   → 500 internal.
      3. Commit, best-effort disable loser RW user.
      4. notify_log.

    The URL is a bearer credential — anyone holding it can take the
    subscription. require_verified_email gates this, the rate limit
    slows credential-stuffing against random short_uuids.
    """
    from app.handlers.android_link_merge import (
        LookupNotFound, MergeBlocked, import_subscription_by_uuid,
    )

    short_uuid = _parse_short_uuid(payload.url)

    async with async_session() as s:
        try:
            merge = await import_subscription_by_uuid(
                s,
                current_user_id=user.id,
                b_rw_short_uuid=short_uuid,
            )
        except LookupNotFound:
            await notify_log(
                f"❌ <b>Android sub-URL import: rw_not_found</b>\n"
                f"user=<code>{user.id}</code> "
                f"short_uuid=<code>{esc(short_uuid)}</code>"
            )
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"code": "rw_not_found"},
            )
        except MergeBlocked as blocked:
            await s.rollback()
            await notify_log(
                _format_notify(
                    result="both_pro_support_needed",
                    user_id=user.id, email=user.email,
                    a_rw_uuid=blocked.details.get("a_rw_uuid"),
                    a_tier="pro",
                    b_rw_uuid=blocked.details.get("t_rw_uuid"),
                    b_tier="pro",
                    chosen=None, disabled=None,
                )
            )
            return LinkByUrlResponse(
                result="both_pro_support_needed",
                a_tier="pro",
                b_tier="pro",
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "link_by_url failed: %s", exc, exc_info=True,
            )
            await s.rollback()
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "internal"},
            )

        await s.commit()

    # Best-effort RW deactivate. Failure does NOT roll back the DB.
    disabled_uuid = merge.get("loser_rw_uuid")
    if merge["result"] in ("merged_pro", "merged_free", "ok") and disabled_uuid:
        try:
            await update_user(user_uuid=disabled_uuid, status="disabled")
        except Exception as exc:
            logger.warning(
                "Failed to disable old RW user %s: %s",
                disabled_uuid, exc,
            )
            await notify_log(
                f"⚠️ <b>Failed to disable old RW user</b>\n"
                f"uuid: <code>{esc(disabled_uuid)}</code>\n"
                f"error: <code>{esc(str(exc)[:300])}</code>"
            )
            disabled_uuid = None  # didn't actually disable; reflect in log

    await notify_log(
        _format_notify(
            result=merge["result"],
            user_id=user.id, email=user.email,
            a_rw_uuid=merge.get("a_rw_uuid"),
            a_tier=merge["a_tier"],
            b_rw_uuid=merge["b_rw_uuid"],
            b_tier=merge["b_tier"],
            chosen=merge["chosen_uuid"],
            disabled=disabled_uuid,
        )
    )

    return LinkByUrlResponse(
        result=merge["result"],
        a_tier=merge["a_tier"],
        b_tier=merge["b_tier"],
    )


def _format_notify(
    *,
    result: str,
    user_id: int,
    email: str | None,
    a_rw_uuid: str | None,
    a_tier: str,
    b_rw_uuid: str | None,
    b_tier: str,
    chosen: str | None,
    disabled: str | None,
) -> str:
    parts = [f"🔗 <b>Android sub-URL import: {esc(result)}</b>"]
    parts.append(
        f"user: <code>{user_id}</code> {esc(email or '—')} "
        f"rw=<code>{esc(a_rw_uuid or '—')}</code> "
        f"tier=<code>{esc(a_tier)}</code>"
    )
    parts.append(
        f"imported: rw=<code>{esc(b_rw_uuid or '—')}</code> "
        f"tier=<code>{esc(b_tier)}</code>"
    )
    if result != "both_pro_support_needed":
        parts.append(
            f"chosen_uuid=<code>{esc(chosen or '—')}</code> "
            f"disabled_uuid=<code>{esc(disabled or '—')}</code>"
        )
    return "\n".join(parts)
```

Make sure `logger` is defined at module level. If the file does NOT have it (check the top of the file from Task 6 — it doesn't), add at the top:

```python
logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_link_by_url_router.py -v
```
Expected: 11 parser tests + 10 endpoint tests = 21 passed.

- [ ] **Step 5: Run the merge test suite — no regressions**

Run:
```bash
python -m pytest tests/test_android_link_merge.py -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add miniapp/backend/android/link_router.py tests/test_link_by_url_router.py
git commit -m "feat(miniapp): POST /api/android/link/by_url

Imports a Remnawave subscription URL into the authenticated account
using the same PRO/FREE merge matrix as the tg-link flow. B-side is
virtual (RW-only); the only DB write is A.vless_uuid = chosen.

- 422 invalid_url on bad URL shape (https/host/path/regex check)
- 404 rw_not_found when short_uuid resolves to nothing
- 200 both_pro_support_needed when both sides hold PRO
- 200 already_owned for self-import
- 200 merged_pro / merged_free / ok otherwise

require_verified_email + 3/min rate limit slow URL-leakage attacks.
RW deactivate of the loser uuid is best-effort outside the DB tx.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Verify full test suite + run common_db tests

**Files:** none modified.

This is the final integration sanity check. Per the spec's known limitation, run the two test directories separately because of the `tests` namespace collision.

- [ ] **Step 1: Run the top-level tests**

Run:
```bash
python -m pytest tests/ -v
```
Expected: all tests green (test_android_link_merge.py + test_link_by_url_router.py).

- [ ] **Step 2: Run the common_db tests**

Run:
```bash
python -m pytest packages/common_db/tests/ -q
```
Expected: 186 passed (no regressions).

- [ ] **Step 3: Quick smoke-import the modified production modules**

Run:
```bash
python -c "from app.handlers.android_link_merge import import_subscription_by_uuid, LookupNotFound, _lookup_a_side_rw; from miniapp.backend.android.link_router import router, _parse_short_uuid; from miniapp.backend.android.schemas_data import LinkByUrlRequest, LinkByUrlResponse; print('ok')"
```
Expected: `ok`.

- [ ] **Step 4: Final commit (only if anything was changed during verification — usually nothing)**

If everything passed without touching code, no commit needed; verification is read-only.

---

## Self-Review Notes

- **Spec coverage:**
  - Section "PRO/FREE classification" → Task 4 (reuses `_classify` unchanged).
  - Section "Resolution matrix" → Task 4 (uses `_decide` with android_id/tg_user_id both = current_user_id; chosen_uuid + result_code consumed; survivor/loser ignored).
  - Section "Self-import short-circuit" → Task 4 step 3 + test 7 (`test_self_import_short_circuits`) and router test `test_self_import_returns_already_owned`.
  - Section "Architecture / new exception" → Task 3.
  - Section "Architecture / `_lookup_a_side_rw`" → Task 3.
  - Section "Architecture / `import_subscription_by_uuid`" → Task 4.
  - Section "Final naming decision (helper)" → Task 3 chooses the single-helper variant as the spec recommends.
  - Section "link_router.py endpoint" → Task 7.
  - Section "URL parsing" → Task 6.
  - Section "Schemas" → Task 5.
  - Section "Notify log format" → Task 7 (`_format_notify`).
  - Section "Transactional boundary" → Task 7 (`async with async_session()` + `commit()` after merge, RW deactivate outside tx).
  - Section "Auth and rate limiting" → Task 7 (require_verified_email + `@limiter.limit("3/minute")`).
  - All 9 edge cases → mix of Task 4 tests + Task 6 parser tests + Task 7 router tests.
  - "Open Tasks / verify api shim" → Task 1.

- **No placeholders:** every code step shows full code; every command is concrete; expected outputs stated.

- **Type consistency:** `import_subscription_by_uuid` signature is stable across Task 4 definition and Task 7 import; `LinkByUrlRequest.url` is `str` (Task 5) and the router calls `_parse_short_uuid(payload.url)` (Task 7); `_format_notify` signature in Task 7 matches its only call site in the same task.

- **Known limitation acknowledged:** the joint `pytest tests/ packages/common_db/tests/` run still fails per the spec's note; Task 8 documents the workaround (run separately).
