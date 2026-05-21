"""Tests for app.handlers.android_link_merge."""
from __future__ import annotations

import pytest

from app.handlers.android_link_merge import _classify


class TestClassify:
    def test_none_when_info_is_none(self):
        assert _classify(None) == "none"

    def test_none_when_info_is_404_sentinel(self):
        assert _classify(404) == "none"

    def test_pro_when_active_and_no_data_limit(self):
        assert _classify({"status": "active", "data_limit": None}) == "pro"

    def test_free_when_active_with_data_limit(self):
        assert _classify({"status": "active", "data_limit": 10 * 1024 ** 3}) == "free"

    def test_free_when_limited(self):
        assert _classify({"status": "limited", "data_limit": None}) == "free"

    def test_free_when_disabled(self):
        assert _classify({"status": "disabled", "data_limit": None}) == "free"


import asyncio

from app.handlers.android_link_merge import _lookup_rw


class TestLookupRw:
    def test_returns_none_when_email_missing(self, fake_remnawave):
        result = asyncio.run(_lookup_rw(email=None, vless_uuid=None,
                                        username=None))
        assert result == (None, None)

    def test_finds_android_by_email(self, fake_remnawave):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        a_info, t_info = asyncio.run(_lookup_rw(
            email="a@x.io", vless_uuid=None, username=None,
        ))
        assert a_info["uuid"] == "a-uuid"
        assert t_info is None

    def test_finds_tg_by_uuid(self, fake_remnawave):
        fake_remnawave.add_user(uuid="t-uuid", status="active",
                                data_limit=10 * 1024 ** 3, username="bob")
        a_info, t_info = asyncio.run(_lookup_rw(
            email=None, vless_uuid="t-uuid", username="bob",
        ))
        assert a_info is None
        assert t_info["uuid"] == "t-uuid"

    def test_falls_back_to_username_when_no_uuid(self, fake_remnawave):
        fake_remnawave.add_user(uuid="t-uuid", status="active",
                                data_limit=None, username="bob")
        _, t_info = asyncio.run(_lookup_rw(
            email=None, vless_uuid=None, username="bob",
        ))
        assert t_info["uuid"] == "t-uuid"

    def test_swallows_exceptions_returns_none(self, fake_remnawave, monkeypatch):
        async def boom(*a, **kw):
            raise RuntimeError("network down")
        import app.api.remnawave.api as rem
        monkeypatch.setattr(rem, "get_user_from_email", boom)
        a_info, _ = asyncio.run(_lookup_rw(
            email="a@x.io", vless_uuid=None, username=None,
        ))
        assert a_info is None


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


from app.handlers.android_link_merge import _decide, MergeBlocked


class TestDecide:
    A_ID, T_ID = 100, 200
    A_UUID, T_UUID = "a-uuid", "t-uuid"

    def _call(self, a_tier, t_tier, *, a_uuid="a-uuid", t_uuid="t-uuid"):
        return _decide(
            a_tier=a_tier, t_tier=t_tier,
            a_rw_uuid=a_uuid, t_rw_uuid=t_uuid,
            android_id=self.A_ID, tg_user_id=self.T_ID,
        )

    def test_pro_vs_pro_blocks(self):
        with pytest.raises(MergeBlocked):
            self._call("pro", "pro")

    def test_pro_vs_free_keeps_android(self):
        survivor, loser, uuid, code = self._call("pro", "free")
        assert (survivor, loser, uuid, code) == (
            self.A_ID, self.T_ID, self.A_UUID, "merged_pro",
        )

    def test_free_vs_pro_keeps_tg(self):
        survivor, loser, uuid, code = self._call("free", "pro")
        assert (survivor, loser, uuid, code) == (
            self.T_ID, self.A_ID, self.T_UUID, "merged_pro",
        )

    def test_free_vs_free_keeps_tg(self):
        survivor, loser, uuid, code = self._call("free", "free")
        assert (survivor, loser, uuid, code) == (
            self.T_ID, self.A_ID, self.T_UUID, "merged_free",
        )

    def test_free_vs_free_tg_uuid_none_falls_back_to_android(self):
        survivor, loser, uuid, code = self._call(
            "free", "free", t_uuid=None,
        )
        assert (survivor, loser, uuid, code) == (
            self.T_ID, self.A_ID, self.A_UUID, "merged_free",
        )

    def test_pro_vs_none_keeps_android(self):
        survivor, loser, uuid, code = self._call("pro", "none", t_uuid=None)
        assert (survivor, loser, uuid, code) == (
            self.A_ID, self.T_ID, self.A_UUID, "ok",
        )

    def test_none_vs_pro_keeps_tg(self):
        survivor, loser, uuid, code = self._call("none", "pro", a_uuid=None)
        assert (survivor, loser, uuid, code) == (
            self.T_ID, self.A_ID, self.T_UUID, "ok",
        )

    def test_none_vs_none_keeps_tg_no_uuid(self):
        survivor, loser, uuid, code = self._call(
            "none", "none", a_uuid=None, t_uuid=None,
        )
        assert (survivor, loser, uuid, code) == (
            self.T_ID, self.A_ID, None, "ok",
        )


import asyncio as _asyncio

from sqlalchemy import select
from common_db.models import User
from app.handlers.android_link_merge import _apply_merge_db


class TestApplyMergeDb:
    def test_copies_missing_fields_from_loser(self, session_factory):
        async def go():
            async with session_factory() as s:
                s.add(User(id=100, tg_id=None, email="a@x.io",
                           password_hash="hash-a"))
                s.add(User(id=200, tg_id=55, username="bob",
                           language="ru", vip=0))
                await s.flush()
                await _apply_merge_db(
                    session=s, survivor_id=200, loser_id=100,
                    tg_id=55, chosen_uuid="kept-uuid",
                )
                survivor = await s.get(User, 200)
                loser = await s.get(User, 100)
                assert loser is None
                assert survivor.tg_id == 55
                assert survivor.email == "a@x.io"
                assert survivor.password_hash == "hash-a"
                assert survivor.username == "bob"
                assert survivor.language == "ru"
                assert survivor.vless_uuid == "kept-uuid"

        _asyncio.run(go())

    def test_reparents_transactions_and_email_verifications(self, session_factory):
        async def go():
            from common_db.models import Transaction, EmailVerification
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io"))
                s.add(User(id=200, tg_id=55))
                s.add(Transaction(
                    transaction_id="tx-1", vless_uuid="v", order_status="paid",
                    delivery_status=1, days_ordered=30, user_id=100,
                    android_user_id=100,
                ))
                s.add(EmailVerification(
                    user_id=100, purpose="tg_link", code_hash="h",
                    created_at="2026-05-19T00:00:00",
                    expires_at="2026-05-19T01:00:00",
                ))
                await s.flush()
                await _apply_merge_db(
                    session=s, survivor_id=200, loser_id=100,
                    tg_id=55, chosen_uuid=None,
                )
                tx = await s.get(Transaction, "tx-1")
                assert tx.user_id == 200
                assert tx.android_user_id == 200
                ev = (await s.execute(
                    select(EmailVerification).where(
                        EmailVerification.purpose == "tg_link"
                    )
                )).scalar_one()
                assert ev.user_id == 200

        _asyncio.run(go())


from app.handlers.android_link_merge import merge_android_and_tg


class TestMergeAndroidAndTg:
    def _seed(self, s):
        s.add(User(id=100, email="a@x.io", password_hash="ph",
                   email_verified_at="2026-05-19T00:00:00"))
        s.add(User(id=200, tg_id=55, username="bob",
                   vless_uuid="t-uuid", language="ru"))

    def test_pro_android_free_tg_survivor_android(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="t-uuid", username="bob",
                                status="active", data_limit=10 * 1024 ** 3)

        async def go():
            async with session_factory() as s:
                self._seed(s)
                await s.flush()
                result = await merge_android_and_tg(
                    s, android_user_id=100, tg_user_id=200, tg_id=55,
                )
                await s.commit()
                return result

        result = _asyncio.run(go())
        assert result["result"] == "merged_pro"
        assert result["survivor_id"] == 100
        assert result["loser_id"] == 200
        assert result["loser_rw_uuid"] == "t-uuid"
        assert result["a_tier"] == "pro"
        assert result["t_tier"] == "free"

    def test_both_pro_raises_merge_blocked(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="t-uuid", username="bob",
                                status="active", data_limit=None)

        async def go():
            async with session_factory() as s:
                self._seed(s)
                await s.flush()
                await merge_android_and_tg(
                    s, android_user_id=100, tg_user_id=200, tg_id=55,
                )

        with pytest.raises(MergeBlocked):
            _asyncio.run(go())

    def test_free_vs_free_keeps_tg(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active",
                                data_limit=5 * 1024 ** 3)
        fake_remnawave.add_user(uuid="t-uuid", username="bob",
                                status="active",
                                data_limit=10 * 1024 ** 3)

        async def go():
            async with session_factory() as s:
                self._seed(s)
                await s.flush()
                result = await merge_android_and_tg(
                    s, android_user_id=100, tg_user_id=200, tg_id=55,
                )
                await s.commit()
                survivor = await s.get(User, result["survivor_id"])
                return result, survivor.vless_uuid, survivor.email

        result, vless_uuid, email = _asyncio.run(go())
        assert result["result"] == "merged_free"
        assert result["survivor_id"] == 200  # TG side
        assert vless_uuid == "t-uuid"
        assert email == "a@x.io"

    def test_pro_android_none_tg_simple_link(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        # TG side: no RW user

        async def go():
            async with session_factory() as s:
                self._seed(s)
                await s.flush()
                result = await merge_android_and_tg(
                    s, android_user_id=100, tg_user_id=200, tg_id=55,
                )
                await s.commit()
                survivor = await s.get(User, result["survivor_id"])
                return result, survivor.vless_uuid, survivor.tg_id

        result, vless_uuid, tg = _asyncio.run(go())
        assert result["result"] == "ok"
        assert result["survivor_id"] == 100  # Android side
        assert vless_uuid == "a-uuid"
        assert tg == 55


import hashlib

from app.handlers.android_link import consume_android_link_code


def _hash(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


class TestConsumeCodeIntegration:
    def test_merged_pro_keeps_android_disables_tg_rw(
        self, with_app_db, fake_remnawave, notify_spy,
    ):
        async def setup():
            from common_db.models import EmailVerification
            async with with_app_db() as s:
                s.add(User(id=100, email="a@x.io"))
                s.add(User(id=200, tg_id=55, username="bob",
                           vless_uuid="t-uuid"))
                s.add(EmailVerification(
                    user_id=100, purpose="tg_link",
                    code_hash=_hash("plain-code"),
                    created_at="2026-05-19T00:00:00",
                    expires_at="2099-01-01T00:00:00",
                ))
                await s.commit()
        _asyncio.run(setup())

        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="t-uuid", username="bob",
                                status="active",
                                data_limit=10 * 1024 ** 3)

        result = _asyncio.run(consume_android_link_code(55, "plain-code"))

        assert result == "merged_pro"
        assert "t-uuid" in fake_remnawave.disabled_calls
        assert any("merged_pro" in m for m in notify_spy)

        async def verify():
            async with with_app_db() as s:
                survivor = await s.get(User, 100)
                loser = await s.get(User, 200)
                return survivor, loser
        survivor, loser = _asyncio.run(verify())
        assert loser is None
        assert survivor.tg_id == 55
        assert survivor.vless_uuid == "a-uuid"

    def test_both_pro_blocked_no_db_changes(
        self, with_app_db, fake_remnawave, notify_spy,
    ):
        async def setup():
            from common_db.models import EmailVerification
            async with with_app_db() as s:
                s.add(User(id=100, email="a@x.io"))
                s.add(User(id=200, tg_id=55, username="bob",
                           vless_uuid="t-uuid"))
                s.add(EmailVerification(
                    id=42, user_id=100, purpose="tg_link",
                    code_hash=_hash("plain-code"),
                    created_at="2026-05-19T00:00:00",
                    expires_at="2099-01-01T00:00:00",
                ))
                await s.commit()
        _asyncio.run(setup())
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="t-uuid", username="bob",
                                status="active", data_limit=None)

        result = _asyncio.run(consume_android_link_code(55, "plain-code"))

        assert result == "both_pro_support_needed"
        assert fake_remnawave.disabled_calls == []
        assert any("both_pro_support_needed" in m for m in notify_spy)

        async def verify():
            from common_db.models import EmailVerification
            async with with_app_db() as s:
                a = await s.get(User, 100)
                t = await s.get(User, 200)
                ev = await s.get(EmailVerification, 42)
                return a, t, ev.used_at
        a, t, used_at = _asyncio.run(verify())
        assert a is not None and t is not None
        # NOT marked used — user can retry after support resolves it.
        assert used_at is None

    def test_simple_link_no_conflict_notifies_ok(
        self, with_app_db, fake_remnawave, notify_spy,
    ):
        async def setup():
            from common_db.models import EmailVerification
            async with with_app_db() as s:
                s.add(User(id=100, email="a@x.io"))
                s.add(EmailVerification(
                    user_id=100, purpose="tg_link",
                    code_hash=_hash("plain-code"),
                    created_at="2026-05-19T00:00:00",
                    expires_at="2099-01-01T00:00:00",
                ))
                await s.commit()
        _asyncio.run(setup())

        result = _asyncio.run(consume_android_link_code(55, "plain-code"))
        assert result == "ok"
        assert any("Android↔TG link: ok" in m for m in notify_spy)

    def test_user_already_linked_skips_merge(
        self, with_app_db, fake_remnawave, notify_spy,
    ):
        async def setup():
            from common_db.models import EmailVerification
            async with with_app_db() as s:
                s.add(User(id=100, tg_id=999, email="a@x.io"))
                s.add(EmailVerification(
                    user_id=100, purpose="tg_link",
                    code_hash=_hash("plain-code"),
                    created_at="2026-05-19T00:00:00",
                    expires_at="2099-01-01T00:00:00",
                ))
                await s.commit()
        _asyncio.run(setup())

        result = _asyncio.run(consume_android_link_code(55, "plain-code"))
        assert result == "user_already_linked"
        assert fake_remnawave.disabled_calls == []
        assert any("user_already_linked" in m for m in notify_spy)

    def test_rw_deactivate_failure_does_not_break_merge(
        self, with_app_db, fake_remnawave, notify_spy,
    ):
        async def setup():
            from common_db.models import EmailVerification
            async with with_app_db() as s:
                s.add(User(id=100, email="a@x.io"))
                s.add(User(id=200, tg_id=55, vless_uuid="t-uuid"))
                s.add(EmailVerification(
                    user_id=100, purpose="tg_link",
                    code_hash=_hash("plain-code"),
                    created_at="2026-05-19T00:00:00",
                    expires_at="2099-01-01T00:00:00",
                ))
                await s.commit()
        _asyncio.run(setup())
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="t-uuid",
                                status="active",
                                data_limit=10 * 1024 ** 3)
        fake_remnawave.update_should_raise = RuntimeError("rw down")

        result = _asyncio.run(consume_android_link_code(55, "plain-code"))
        assert result == "merged_pro"
        assert any("Failed to disable old RW user" in m for m in notify_spy)


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
