"""Tests for the account_linking package (Android<->Telegram merge)."""
from __future__ import annotations

import pytest

from account_linking import _classify


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

from account_linking import _lookup_rw


class TestLookupRw:
    def test_returns_none_when_email_missing(self, fake_remnawave):
        result = asyncio.run(_lookup_rw(
            a_rw_id=None, t_rw_id=None, email=None, username=None,
        ))
        assert result == (None, None)

    def test_finds_android_by_email(self, fake_remnawave):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None, rw_id=11)
        a_info, t_info = asyncio.run(_lookup_rw(
            a_rw_id=None, t_rw_id=None, email="a@x.io", username=None,
        ))
        assert a_info["rw_id"] == 11
        assert t_info is None

    def test_finds_tg_by_id(self, fake_remnawave):
        fake_remnawave.add_user(uuid="t-uuid", status="active",
                                data_limit=10 * 1024 ** 3, username="bob",
                                rw_id=22)
        a_info, t_info = asyncio.run(_lookup_rw(
            a_rw_id=None, t_rw_id=22, email=None, username="bob",
        ))
        assert a_info is None
        assert t_info["rw_id"] == 22

    def test_falls_back_to_username_when_no_uuid(self, fake_remnawave):
        fake_remnawave.add_user(uuid="t-uuid", status="active",
                                data_limit=None, username="bob",
                                rw_id=22, telegram_id=55)
        _, t_info = asyncio.run(_lookup_rw(
            a_rw_id=None, t_rw_id=None, email=None, username="bob",
            expected_telegram_id=55,
        ))
        assert t_info["rw_id"] == 22

    def test_propagates_lookup_outage(self, fake_remnawave, monkeypatch):
        async def boom(*a, **kw):
            raise RuntimeError("network down")
        from remnawave_client import api as rem
        monkeypatch.setattr(rem, "get_user_from_email", boom)
        with pytest.raises(RuntimeError, match="network down"):
            asyncio.run(_lookup_rw(
                a_rw_id=None, t_rw_id=None, email="a@x.io", username=None,
            ))


from account_linking import (
    LookupNotFound,
    _lookup_a_side_rw,
)


class TestLookupASideRw:
    """A-side-only lookup helper used by import_subscription_by_uuid."""

    def test_returns_none_when_both_identifiers_missing(self, fake_remnawave):
        result = asyncio.run(_lookup_a_side_rw(rw_id=None, email=None))
        assert result is None

    def test_finds_by_rw_id_first(self, fake_remnawave):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None, rw_id=11)
        result = asyncio.run(_lookup_a_side_rw(
            rw_id=11, email="a@x.io",
        ))
        assert result is not None
        assert result["rw_id"] == 11

    def test_falls_back_to_email_when_uuid_missing(self, fake_remnawave):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        result = asyncio.run(_lookup_a_side_rw(
            rw_id=None, email="a@x.io",
        ))
        assert result is not None
        assert result["rw_id"] == 1

    def test_propagates_lookup_outage(self, fake_remnawave, monkeypatch):
        async def boom(*a, **kw):
            raise RuntimeError("network down")
        from remnawave_client import api as rem
        monkeypatch.setattr(rem, "get_user_from_id", boom)
        with pytest.raises(RuntimeError, match="network down"):
            asyncio.run(_lookup_a_side_rw(
                rw_id=11, email=None,
            ))


class TestLookupNotFound:
    def test_is_an_exception(self):
        assert issubclass(LookupNotFound, Exception)

    def test_carries_short_uuid_detail(self):
        exc = LookupNotFound("missing-short")
        assert "missing-short" in str(exc)


from account_linking import _decide, MergeBlocked


class TestDecide:
    A_ID, T_ID = 100, 200
    A_RW_ID, T_RW_ID = 11, 22

    def _call(self, a_tier, t_tier, *, a_rw_id=11, t_rw_id=22):
        return _decide(
            a_tier=a_tier, t_tier=t_tier,
            a_rw_id=a_rw_id, t_rw_id=t_rw_id,
            android_id=self.A_ID, tg_user_id=self.T_ID,
        )

    def test_pro_vs_pro_keeps_tg_and_both_profiles(self):
        assert self._call("pro", "pro") == (
            self.T_ID, self.A_ID, self.T_RW_ID, "merged_pro",
        )

    def test_pro_vs_free_keeps_android(self):
        survivor, loser, uuid, code = self._call("pro", "free")
        assert (survivor, loser, uuid, code) == (
            self.T_ID, self.A_ID, self.A_RW_ID, "merged_pro",
        )

    def test_free_vs_pro_keeps_tg(self):
        survivor, loser, uuid, code = self._call("free", "pro")
        assert (survivor, loser, uuid, code) == (
            self.T_ID, self.A_ID, self.T_RW_ID, "merged_pro",
        )

    def test_free_vs_free_keeps_tg(self):
        survivor, loser, uuid, code = self._call("free", "free")
        assert (survivor, loser, uuid, code) == (
            self.T_ID, self.A_ID, self.T_RW_ID, "merged_free",
        )

    def test_free_vs_free_tg_uuid_none_falls_back_to_android(self):
        survivor, loser, uuid, code = self._call(
            "free", "free", t_rw_id=None,
        )
        assert (survivor, loser, uuid, code) == (
            self.T_ID, self.A_ID, self.A_RW_ID, "merged_free",
        )

    def test_pro_vs_none_keeps_android(self):
        survivor, loser, uuid, code = self._call("pro", "none", t_rw_id=None)
        assert (survivor, loser, uuid, code) == (
            self.T_ID, self.A_ID, self.A_RW_ID, "ok",
        )

    def test_none_vs_pro_keeps_tg(self):
        survivor, loser, uuid, code = self._call("none", "pro", a_rw_id=None)
        assert (survivor, loser, uuid, code) == (
            self.T_ID, self.A_ID, self.T_RW_ID, "ok",
        )

    def test_none_vs_none_keeps_tg_no_uuid(self):
        survivor, loser, uuid, code = self._call(
            "none", "none", a_rw_id=None, t_rw_id=None,
        )
        assert (survivor, loser, uuid, code) == (
            self.T_ID, self.A_ID, None, "ok",
        )


import asyncio as _asyncio

from sqlalchemy import select, text
from common_db.models import User
from account_linking import _apply_merge_db


class TestApplyMergeDb:
    def test_copies_missing_fields_from_loser(self, session_factory):
        async def go():
            async with session_factory() as s:
                s.add(User(id=100, tg_id=None, email="a@x.io",
                           password_hash="hash-a", vless_uuid="legacy-a"))
                s.add(User(id=200, tg_id=55, username="bob",
                           language="ru", vip=0))
                await s.flush()
                await _apply_merge_db(
                    session=s, survivor_id=200, loser_id=100,
                    tg_id=55, chosen_rw_id=11,
                )
                survivor = await s.get(User, 200)
                loser = await s.get(User, 100)
                assert loser is None
                assert survivor.tg_id == 55
                assert survivor.email == "a@x.io"
                assert survivor.password_hash == "hash-a"
                assert survivor.username == "bob"
                assert survivor.language == "ru"
                assert survivor.vless_uuid == "legacy-a"
                assert survivor.rw_id == 11

        _asyncio.run(go())

    @pytest.mark.parametrize(
        ("survivor_primary", "loser_primary", "expected_rw_id"),
        [(True, True, 22), (False, True, 11), (False, False, 11)],
    )
    def test_preserves_subscriptions_primary_and_sums_credits(
        self, session_factory, survivor_primary, loser_primary, expected_rw_id,
    ):
        async def go():
            from common_db.models import UserSubscription

            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", bonus_credits=7))
                s.add(User(id=200, tg_id=55, bonus_credits=5))
                s.add(UserSubscription(
                    user_id=100, rw_id=11, source="android",
                    is_primary=loser_primary, created_at="2026-01-01", updated_at="2026-01-01",
                ))
                s.add(UserSubscription(
                    user_id=200, rw_id=22, source="telegram",
                    is_primary=survivor_primary, created_at="2026-02-01", updated_at="2026-02-01",
                ))
                await s.flush()
                await _apply_merge_db(
                    session=s, survivor_id=200, loser_id=100,
                    tg_id=55, chosen_rw_id=99,
                )
                survivor = await s.get(User, 200)
                rows = (await s.execute(text(
                    "SELECT rw_id, is_primary FROM user_subscriptions "
                    "WHERE user_id = 200 ORDER BY id"
                ))).all()
                return survivor, rows

        survivor, rows = _asyncio.run(go())
        assert survivor.bonus_credits == 12
        assert survivor.rw_id == expected_rw_id
        assert len(rows) == 2
        assert sum(bool(row.is_primary) for row in rows) == 1

    def test_user_owned_table_metadata_is_fully_covered(self):
        from common_db import Base
        from account_linking.merge import _all_user_owned_tables

        modeled = {
            table.name
            for table in Base.metadata.tables.values()
            if "user_id" in table.c
            and any(fk.target_fullname == "users.id" for fk in table.c.user_id.foreign_keys)
        }
        covered = set(_all_user_owned_tables()) | {"user_subscriptions"}
        assert modeled <= covered
        assert {
            "credit_ledger", "android_fcm_tokens", "push_campaign_deliveries",
            "web_authorization_codes", "subscription_transfers",
        } <= covered

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
                    tg_id=55, chosen_rw_id=None,
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


from account_linking import merge_android_and_tg


class TestMergeAndroidAndTg:
    def _seed(self, s):
        s.add(User(id=100, email="a@x.io", password_hash="ph", rw_id=1,
                   email_verified_at="2026-05-19T00:00:00"))
        s.add(User(id=200, tg_id=55, username="bob",
                   vless_uuid="t-uuid", rw_id=2, language="ru"))

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
        assert result["survivor_id"] == 200
        assert result["loser_id"] == 100
        assert result["loser_rw_id"] is None
        assert result["a_tier"] == "pro"
        assert result["t_tier"] == "free"

    def test_both_pro_merges_and_preserves_both(
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
                result = await merge_android_and_tg(
                    s, android_user_id=100, tg_user_id=200, tg_id=55,
                )
                await s.commit()
                count = await s.scalar(text(
                    "SELECT COUNT(*) FROM user_subscriptions WHERE user_id = 200"
                ))
                return result, count

        result, count = _asyncio.run(go())
        assert result["result"] == "merged_pro"
        assert result["survivor_id"] == 200
        assert result["loser_rw_id"] is None
        assert count == 2

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
                return result, survivor.vless_uuid, survivor.rw_id, survivor.tg_id

        result, legacy_uuid, rw_id, tg = _asyncio.run(go())
        assert result["result"] == "ok"
        assert result["survivor_id"] == 200  # Telegram row always survives
        assert legacy_uuid == "t-uuid"
        assert rw_id == 1
        assert tg == 55


from account_linking import merge_tg_into_email


class TestMergeTgIntoEmail:
    def _seed(self, s):
        s.add(User(id=100, email="a@x.io", password_hash="ph", rw_id=1,
                   email_verified_at="2026-05-19T00:00:00"))
        s.add(User(id=200, tg_id=55, username="bob",
                   vless_uuid="t-uuid", rw_id=2, language="ru"))

    def test_email_is_survivor_and_keeps_primary(
        self, session_factory, fake_remnawave,
    ):
        from common_db.models import UserSubscription

        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None, rw_id=1)
        fake_remnawave.add_user(uuid="t-uuid", username="bob",
                                status="active", data_limit=None, rw_id=2,
                                telegram_id=55)

        async def go():
            async with session_factory() as s:
                self._seed(s)
                s.add(UserSubscription(
                    user_id=100, rw_id=1, source="android",
                    is_primary=True, created_at="2026-01-01",
                    updated_at="2026-01-01",
                ))
                s.add(UserSubscription(
                    user_id=200, rw_id=2, source="telegram",
                    is_primary=True, created_at="2026-02-01",
                    updated_at="2026-02-01",
                ))
                await s.flush()
                result = await merge_tg_into_email(
                    s, email_user_id=100, tg_user_id=200, tg_id=55,
                )
                await s.commit()
                survivor = await s.get(User, 100)
                loser = await s.get(User, 200)
                rows = (await s.execute(text(
                    "SELECT rw_id, is_primary FROM user_subscriptions "
                    "WHERE user_id = 100 ORDER BY rw_id"
                ))).all()
                return result, survivor, loser, rows

        result, survivor, loser, rows = _asyncio.run(go())
        assert result["result"] == "merged_pro"
        assert result["survivor_id"] == 100
        assert result["loser_id"] == 200
        assert loser is None
        assert survivor.tg_id == 55
        assert survivor.email == "a@x.io"
        assert survivor.username == "bob"
        assert len(rows) == 2
        primary = [r for r in rows if r.is_primary]
        assert len(primary) == 1
        assert primary[0].rw_id == 1  # email primary kept
        non_primary = [r for r in rows if not r.is_primary]
        assert len(non_primary) == 1
        assert non_primary[0].rw_id == 2

    def test_tg_only_sub_becomes_primary_when_email_has_none(
        self, session_factory, fake_remnawave,
    ):
        from common_db.models import UserSubscription

        fake_remnawave.add_user(uuid="t-uuid", username="bob",
                                status="active", data_limit=None, rw_id=2,
                                telegram_id=55)

        async def go():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", password_hash="ph",
                           email_verified_at="2026-05-19T00:00:00"))
                s.add(User(id=200, tg_id=55, username="bob",
                           vless_uuid="t-uuid", rw_id=2))
                s.add(UserSubscription(
                    user_id=200, rw_id=2, source="telegram",
                    is_primary=True, created_at="2026-02-01",
                    updated_at="2026-02-01",
                ))
                await s.flush()
                result = await merge_tg_into_email(
                    s, email_user_id=100, tg_user_id=200, tg_id=55,
                )
                await s.commit()
                survivor = await s.get(User, 100)
                rows = (await s.execute(text(
                    "SELECT rw_id, is_primary FROM user_subscriptions "
                    "WHERE user_id = 100"
                ))).all()
                return result, survivor, rows

        result, survivor, rows = _asyncio.run(go())
        assert result["result"] == "merged_pro"
        assert result["survivor_id"] == 100
        assert survivor.tg_id == 55
        assert len(rows) == 1
        assert bool(rows[0].is_primary)
        assert rows[0].rw_id == 2

    def test_neither_side_has_rw_still_links_tg(
        self, session_factory, fake_remnawave,
    ):
        async def go():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", password_hash="ph"))
                s.add(User(id=200, tg_id=55, username="bob"))
                await s.flush()
                result = await merge_tg_into_email(
                    s, email_user_id=100, tg_user_id=200, tg_id=55,
                )
                await s.commit()
                survivor = await s.get(User, 100)
                loser = await s.get(User, 200)
                return result, survivor, loser

        result, survivor, loser = _asyncio.run(go())
        assert result["result"] == "ok"
        assert result["survivor_id"] == 100
        assert loser is None
        assert survivor.tg_id == 55
        assert survivor.username == "bob"


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
                s.add(User(id=100, email="a@x.io", rw_id=1))
                s.add(User(id=200, tg_id=55, username="bob",
                           vless_uuid="t-uuid", rw_id=2))
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
        assert fake_remnawave.disabled_calls == []
        assert any("merged_pro" in m for m in notify_spy)

        async def verify():
            async with with_app_db() as s:
                survivor = await s.get(User, 200)
                loser = await s.get(User, 100)
                return survivor, loser
        survivor, loser = _asyncio.run(verify())
        assert loser is None
        assert survivor.tg_id == 55
        assert survivor.vless_uuid == "t-uuid"

    def test_both_pro_merges_without_disabling_profiles(
        self, with_app_db, fake_remnawave, notify_spy,
    ):
        async def setup():
            from common_db.models import EmailVerification
            async with with_app_db() as s:
                s.add(User(id=100, email="a@x.io", rw_id=1))
                s.add(User(id=200, tg_id=55, username="bob",
                           vless_uuid="t-uuid", rw_id=2))
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

        assert result == "merged_pro"
        assert fake_remnawave.disabled_calls == []
        assert any("merged_pro" in m for m in notify_spy)

        async def verify():
            from common_db.models import EmailVerification
            async with with_app_db() as s:
                a = await s.get(User, 100)
                t = await s.get(User, 200)
                ev = await s.get(EmailVerification, 42)
                return a, t, ev.used_at
        a, t, used_at = _asyncio.run(verify())
        assert a is None and t is not None
        assert used_at is not None

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
                s.add(User(id=100, email="a@x.io", rw_id=1))
                s.add(User(id=200, tg_id=55, vless_uuid="t-uuid", rw_id=2))
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
        assert fake_remnawave.disabled_calls == []
        assert not any("Failed to disable old RW user" in m for m in notify_spy)


class TestFakeRemnawaveShortUuid:
    """Sanity-check the FakeRemnawave short_uuid extension before the
    real import_subscription_by_uuid tests rely on it."""

    def test_short_uuid_lookup_returns_full_record(self, fake_remnawave):
        fake_remnawave.add_user(
            uuid="b-uuid", short_uuid="sN_xxxxxxxxxxxx",
            status="active", data_limit=None, email="b@x.io",
        )
        from remnawave_client import api as rem
        rec = _asyncio.run(rem.get_user_by_short_uuid_raw("sN_xxxxxxxxxxxx"))
        assert rec is not None
        assert rec["id"] == 1
        assert rec["rw_id"] == 1
        assert rec["status"] == "active"

    def test_short_uuid_lookup_returns_none_for_unknown(self, fake_remnawave):
        from remnawave_client import api as rem
        rec = _asyncio.run(rem.get_user_by_short_uuid_raw("missing"))
        assert rec is None


from account_linking import import_subscription_by_uuid


class TestImportSubscriptionByUuid:
    """End-to-end matrix coverage for the by_url import flow."""

    SHORT = "sN_RHMk6BGv-RJ8g"

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
                return result, survivor.rw_id

        return _asyncio.run(go())

    def test_pro_a_free_b_keeps_a_disables_b(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                email="b@x.io",
                                status="active",
                                data_limit=10 * 1024 ** 3)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid", rw_id=1))
                await s.commit()
        _asyncio.run(seed())

        result, rw_id = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
            claimed_email="b@x.io",
        )
        assert result["result"] == "merged_pro"
        assert result["a_tier"] == "pro"
        assert result["b_tier"] == "free"
        assert result["chosen_rw_id"] == 1
        assert result["loser_rw_id"] is None
        assert rw_id == 1

    def test_free_a_pro_b_keeps_b_disables_a(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active",
                                data_limit=5 * 1024 ** 3)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                email="b@x.io",
                                status="active", data_limit=None)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid", rw_id=1))
                await s.commit()
        _asyncio.run(seed())

        result, rw_id = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
            claimed_email="b@x.io",
        )
        assert result["result"] == "merged_pro"
        assert result["a_tier"] == "free"
        assert result["b_tier"] == "pro"
        assert result["chosen_rw_id"] == 1
        assert result["loser_rw_id"] is None
        assert rw_id == 1

    def test_free_a_free_b_keeps_b_disables_a(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active",
                                data_limit=5 * 1024 ** 3)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                email="b@x.io",
                                status="active",
                                data_limit=10 * 1024 ** 3)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid", rw_id=1))
                await s.commit()
        _asyncio.run(seed())

        result, rw_id = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
            claimed_email="b@x.io",
        )
        assert result["result"] == "merged_free"
        assert result["chosen_rw_id"] == 1
        assert result["loser_rw_id"] is None
        assert rw_id == 1

    def test_pro_a_pro_b_preserves_both_and_primary(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                email="b@x.io",
                                status="active", data_limit=None)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid", rw_id=1))
                await s.commit()
        _asyncio.run(seed())

        async def go():
            async with session_factory() as s:
                result = await import_subscription_by_uuid(
                    s, current_user_id=100, b_rw_short_uuid=self.SHORT,
                    claimed_email="b@x.io",
                )
                await s.commit()
                survivor = await s.get(User, 100)
                count = await s.scalar(text(
                    "SELECT COUNT(*) FROM user_subscriptions WHERE user_id = 100"
                ))
                return result, survivor.rw_id, count

        result, rw_id, count = _asyncio.run(go())
        assert result["result"] == "merged_pro"
        assert rw_id == 1
        assert count == 2
        assert fake_remnawave.disabled_calls == []

    def test_a_none_b_free_simple_takeover(
        self, session_factory, fake_remnawave,
    ):
        # A has neither rw_id nor email → tier "none".
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                email="b@x.io",
                                status="active",
                                data_limit=10 * 1024 ** 3)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, tg_id=55))
                await s.commit()
        _asyncio.run(seed())

        result, rw_id = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
            claimed_email="b@x.io",
        )
        assert result["result"] == "ok"
        assert result["a_tier"] == "none"
        assert result["b_tier"] == "free"
        assert result["chosen_rw_id"] == 1
        assert result["loser_rw_id"] is None
        assert rw_id == 1

    def test_a_none_b_pro_simple_takeover(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                email="b@x.io",
                                status="active", data_limit=None)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, tg_id=55))
                await s.commit()
        _asyncio.run(seed())

        result, rw_id = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
            claimed_email="b@x.io",
        )
        assert result["result"] == "ok"
        assert result["a_tier"] == "none"
        assert result["b_tier"] == "pro"
        assert result["chosen_rw_id"] == 1
        assert result["loser_rw_id"] is None
        assert rw_id == 1

    def test_self_import_short_circuits(
        self, session_factory, fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", short_uuid=self.SHORT,
                                email="a@x.io",
                                status="active", data_limit=None)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid", rw_id=1))
                await s.commit()
        _asyncio.run(seed())

        result, rw_id = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
            claimed_email="a@x.io",
        )
        assert result["result"] == "already_owned"
        assert result["chosen_rw_id"] == 1
        assert result["loser_rw_id"] is None
        assert rw_id == 1
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
                        claimed_email="b@x.io",
                    )
                survivor = await s.get(User, 100)
                return survivor.vless_uuid

        vless = _asyncio.run(go())
        assert vless == "a-uuid"

    def test_a_email_fallback_when_rw_id_missing(
        self, session_factory, fake_remnawave,
    ):
        """A.rw_id is None but A.email resolves to PRO in RW.

        Verifies the A-side email-fallback branch of _lookup_a_side_rw.
        Expected outcome: PRO A + FREE B → merged_pro, chosen_rw_id=A.id.
        """
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=self.SHORT,
                                email="b@x.io",
                                status="active",
                                data_limit=10 * 1024 ** 3)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io"))  # no rw_id
                await s.commit()
        _asyncio.run(seed())

        result, rw_id = self._run(
            session_factory, current_user_id=100, short_uuid=self.SHORT,
            claimed_email="b@x.io",
        )
        assert result["result"] == "merged_pro"
        assert result["chosen_rw_id"] == 1
        assert result["loser_rw_id"] is None
        assert rw_id == 1

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

        result, rw_id = self._run(
            session_factory,
            current_user_id=100,
            short_uuid=self.SHORT,
            claimed_email="  alice@x.io  ",
        )
        assert result["result"] == "ok"
        assert result["chosen_rw_id"] == 1
        assert rw_id == 1

    def test_self_import_with_wrong_email_raises_lookup_not_found(
        self, session_factory, fake_remnawave,
    ):
        """A.rw_id == B.id (would short-circuit to already_owned),
        but claimed_email doesn't match B's RW email. Email check must run
        BEFORE the self-import short-circuit, so this raises LookupNotFound.
        """
        fake_remnawave.add_user(uuid="a-uuid", short_uuid=self.SHORT,
                                email="a@x.io",
                                status="active", data_limit=None)

        async def seed():
            async with session_factory() as s:
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid", rw_id=1))
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
                s.add(User(id=100, email="a@x.io", vless_uuid="a-uuid", rw_id=1))
                await s.commit()
        _asyncio.run(seed())

        result, rw_id = self._run(
            session_factory,
            current_user_id=100,
            short_uuid=self.SHORT,
            claimed_email="a@x.io",
        )
        assert result["result"] == "already_owned"
        assert rw_id == 1
