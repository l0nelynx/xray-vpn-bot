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
