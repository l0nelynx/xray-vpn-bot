import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
from common_db.models import User, Promo, PromoRedemption, PromoSettings, Transaction
from common_db.models.referral_recovery import ReferralRecovery, ReferralNotice
from common_db.referral_worker import send_notices


@pytest.fixture
def recovery_client(tmp_path, monkeypatch):
    from dashboard.backend.routers import tg_admin
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'recovery.sqlite'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def seed():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with factory() as session:
            session.add_all([
                ReferralRecovery(id=1, status="ready"),
                PromoSettings(id=1, points_reward_per_30=30, reward_cap_points=1800),
                User(id=1, tg_id=100), User(id=2, tg_id=200),
                Promo(id=1, tg_id=100, promo_code="REF", promo_type="referral"),
                PromoRedemption(id=1, tg_id=200, promo_code="REF", promo_type="referral", created_at="2026-01-01"),
                Transaction(transaction_id="old", user_id=2, vless_uuid="none", order_status="confirmed",
                            delivery_status=1, days_ordered=30, amount=100, payment_method="CARD", created_at="2026-02-01"),
            ])
            await session.commit()
    asyncio.run(seed())
    monkeypatch.setattr(tg_admin, "async_session", factory)
    app = FastAPI()
    app.include_router(tg_admin.router)
    app.dependency_overrides[tg_admin.get_current_user] = lambda: "admin"
    with TestClient(app) as client:
        yield client, app, factory, tg_admin
    asyncio.run(engine.dispose())


def test_review_confirm_report_retry_without_duplicate_points(recovery_client):
    client, _, factory, _ = recovery_client
    base = "/api/tg-admin/referral-recovery"
    snapshot = client.post(base + "/preview", json={}).json()
    assert snapshot["plan"]["total"] == 33
    body = {"preview_id": snapshot["id"], "reviewed": False}
    assert client.post(base + "/execute", json=body).status_code == 400
    body["reviewed"] = True
    for _ in range(2):
        assert client.post(base + "/execute", json=body).status_code == 200
    assert client.post(base + "/preview", json={}).status_code == 409
    sender = AsyncMock(return_value=("failed", "Forbidden"))
    asyncio.run(send_notices(factory, sender))
    report = client.get(base).json()
    assert report["status"] == "executed"
    assert report["messages"]["failed"] == 1
    assert client.post(base + "/retry-messages").json() == {"queued": 1}
    sender = AsyncMock(return_value=("sent", None))
    asyncio.run(send_notices(factory, sender))
    assert client.get(base).json()["messages"]["sent"] == 1
    assert client.post(base + "/retry-messages").json() == {"queued": 0}

    async def check():
        async with factory() as s:
            assert (await s.get(User, 1)).bonus_credits == 33
            assert (await s.get(ReferralNotice, "recovery:1")).status == "sent"
    asyncio.run(check())


def test_every_recovery_endpoint_requires_admin(recovery_client):
    client, app, _, tg_admin = recovery_client
    del app.dependency_overrides[tg_admin.get_current_user]
    base = "/api/tg-admin/referral-recovery"
    assert client.get(base).status_code in (401, 403)
    for suffix, body in [("preview", {}), ("execute", {"preview_id": "x", "reviewed": True}), ("retry-messages", {})]:
        assert client.post(base + "/" + suffix, json=body).status_code in (401, 403)


def test_old_preview_and_bad_adjustments_are_rejected(recovery_client):
    client, _, _, _ = recovery_client
    base = "/api/tg-admin/referral-recovery"
    assert client.post(base + "/preview", json={"manual_adjustments": {"1": -10}}).status_code == 409
    first = client.post(base + "/preview", json={}).json()
    client.post(base + "/preview", json={})
    assert client.post(base + "/execute", json={"preview_id": first["id"], "reviewed": True}).status_code == 409


def test_migration_reserves_old_deliveries_and_precredited_pending_orders():
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).resolve().parents[1] / "alembic/versions/0044_referral_recovery.py"
    spec = importlib.util.spec_from_file_location("referral_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE transactions (transaction_id VARCHAR(100) PRIMARY KEY, delivery_status INTEGER, order_status VARCHAR(50), payment_method VARCHAR(50))")
            conn.exec_driver_sql("INSERT INTO transactions VALUES ('old',1,'confirmed','CARD'), ('pending',0,'confirmed','CARD'), ('credits',0,'confirmed','BONUS_CREDITS'), ('cancelled',0,'cancelled','BONUS_CREDITS')")
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            assert set(conn.execute(sa.text("SELECT transaction_id FROM referral_receipts")).scalars()) == {"old", "credits"}
            assert conn.execute(sa.text("SELECT status FROM referral_recovery")).scalar() == "ready"
            assert conn.execute(sa.text("SELECT COUNT(*) FROM referral_notices")).scalar() == 0
            migration.downgrade()
            assert not sa.inspect(conn).has_table("referral_recovery")
    finally:
        engine.dispose()
