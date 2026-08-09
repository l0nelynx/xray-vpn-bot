"""Seller-bot DB module — runtime + (legacy) model surface.

Model definitions have moved to `common_db.models` (packages/common_db) so
the seller bot, dashboard and miniapp share a single ORM and a single
`Base.metadata`. The classes are re-exported here unchanged for backwards
compatibility — existing imports like

    from app.database.models import User, Transaction, async_session

keep working. Alembic also reads `app.database.models.Base.metadata` for
autogeneration; after this shim that's `common_db.Base.metadata`, which
collects every shared model.

What stays in this file:
- the runtime `engine` / `async_session` (bound to the seller-bot's DB URL)
- the startup orchestrator `async_main()` and its `_seed_*` helpers
"""
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Re-export the shared Base + every model from common_db. Imports below
# refer to these names directly; we
# also expose them in __all__ so legacy `from app.database.models import X`
# keeps working for every class.
from common_db import Base  # noqa: F401
from common_db.models import (  # noqa: F401
    AndroidFcmToken,
    AppRuntimeSettings,
    BotFeatureFlags,
    CacheVersion,
    CrmCampaign,
    CrmCampaignDelivery,
    CreditLedger,
    DisabledUser,
    EmailVerification,
    GooglePlayPurchase,
    GooglePlaySku,
    MenuButton,
    MenuScreen,
    MiniappUxEvent,
    PaymentIntegration,
    Promo,
    PromoRedemption,
    PromoSettings,
    PushCampaign,
    PushCampaignDelivery,
    RefreshToken,
    SupportAttachment,
    SupportMessage,
    SupportTicket,
    TelegramLinkCode,
    TelmtFreeParams,
    Transaction,
    User,
    WebAppMenuNode,
)

from app.database.url import async_db_url

DB_URL = async_db_url(default_sqlite_path='db.sqlite3')

_pool_kwargs: dict = {}
if not DB_URL.startswith("sqlite"):
    # SQLAlchemy's asyncpg default is pool_size=5 + max_overflow=10 (15 max).
    # Bump it so a burst of concurrent requests doesn't start queuing for a
    # connection before CPU/memory are anywhere near their limits.
    # pool_size/max_overflow are QueuePool-only kwargs — sqlite uses a
    # different poolclass, hence the guard.
    _pool_kwargs = {"pool_size": 10, "max_overflow": 10}

engine = create_async_engine(url=DB_URL, pool_pre_ping=True, **_pool_kwargs)

async_session = async_sessionmaker(engine)


__all__ = [
    # runtime
    "Base",
    "DB_URL",
    "engine",
    "async_session",
    "async_main",
    # models (re-exported from common_db.models)
    "AndroidFcmToken",
    "AppRuntimeSettings",
    "BotFeatureFlags",
    "CacheVersion",
    "CrmCampaign",
    "CrmCampaignDelivery",
    "CreditLedger",
    "DisabledUser",
    "EmailVerification",
    "GooglePlayPurchase",
    "GooglePlaySku",
    "MenuButton",
    "MenuScreen",
    "MiniappUxEvent",
    "PaymentIntegration",
    "Promo",
    "PromoRedemption",
    "PromoSettings",
    "PushCampaign",
    "PushCampaignDelivery",
    "RefreshToken",
    "SupportAttachment",
    "SupportMessage",
    "SupportTicket",
    "TelegramLinkCode",
    "TelmtFreeParams",
    "Transaction",
    "User",
    "WebAppMenuNode",
]


async def async_main():
    """Apply Alembic migrations and seed default rows.

    Schema management lives entirely in alembic/. Legacy idempotent ALTERs
    have been consolidated into revision 0006_postgres_compat.
    """
    from migrations_runner import upgrade_to_head

    upgrade_to_head()

    # Seed cache_version row and tariff/menu data if empty
    await _seed_cache_version()
    await _seed_menus()
    await _backfill_screen_texts()
    await _seed_telemt_free_params()
    await _seed_promo_settings()
    await _seed_bot_feature_flags()
    await _seed_runtime_settings()


async def _seed_runtime_settings():
    """Ensure app_runtime_settings singleton exists (migration also inserts)."""
    from common_db.repo.runtime import get_runtime_settings

    async with async_session() as session:
        await get_runtime_settings(session)
        await session.commit()


async def _seed_cache_version():
    """Ensure cache_version row exists."""
    from sqlalchemy import select, func
    async with async_session() as session:
        count = await session.scalar(select(func.count()).select_from(CacheVersion))
        if not count:
            session.add(CacheVersion(id=1, version=0))
            await session.commit()


async def _seed_menus():
    """Seed the editable Telegram menu screens when they are absent."""
    from sqlalchemy import select, func
    import app.locale.lang_ru as lang_ru
    import app.locale.lang_en as lang_en

    async with async_session() as session:
        count = await session.scalar(select(func.count()).select_from(MenuScreen))
        if count and count > 0:
            return

        # Seed menu screens with buttons
        screens_data = [
            {
                "slug": "main_new", "name": "Main Menu (New User)",
                "message_text_ru": lang_ru.start_base + lang_ru.start_new + lang_ru.start_agreement,
                "message_text_en": lang_en.start_base + lang_en.start_new + lang_en.start_agreement,
                "is_system": True,
                "buttons": [
                    ("🔒 Купить Premium", "🔒 Buy Premium", None, 0, "tariff"),
                    ("📱 Инструкция", "📱 Instructions", "Others", 1),
                    ("🆓 Бесплатная версия", "🆓 Free Version", "Free", 2),
                    ("👥 Пригласить друзей", "👥 Invite Friends", "Invite_Friends", 3),
                    ("⚙️ Настройки", "⚙️ Settings", "Settings", 4),
                ]
            },
            {
                "slug": "main_pro", "name": "Main Menu (Pro User)",
                "message_text_ru": lang_ru.start_pro + "{sub_info}" + lang_ru.start_agreement,
                "message_text_en": lang_en.start_pro + "{sub_info}" + lang_en.start_agreement,
                "is_system": True,
                "buttons": [
                    ("🔄 Продлить подписку", "🔄 Extend Subscription", None, 0, "tariff"),
                    ("📱 Инструкция", "📱 Instructions", "Others", 1),
                    ("📊 Моя подписка", "📊 My Subscription", "Sub_Info", 2),
                    ("📲 Устройства", "📲 Devices", "Devices", 3),
                    ("👥 Пригласить друзей", "👥 Invite Friends", "Invite_Friends", 4),
                    ("⚙️ Настройки", "⚙️ Settings", "Settings", 5),
                ]
            },
            {
                "slug": "main_free", "name": "Main Menu (Free User)",
                "message_text_ru": lang_ru.start_free + "{sub_info}" + lang_ru.start_agreement,
                "message_text_en": lang_en.start_free + "{sub_info}" + lang_en.start_agreement,
                "is_system": True,
                "buttons": [
                    ("🔒 Купить Premium", "🔒 Buy Premium", None, 0, "tariff"),
                    ("📱 Инструкция", "📱 Instructions", "Others", 1),
                    ("📊 Моя подписка", "📊 My Subscription", "Sub_Info", 2),
                    ("📲 Устройства", "📲 Devices", "Devices", 3),
                    ("👥 Пригласить друзей", "👥 Invite Friends", "Invite_Friends", 4),
                    ("⚙️ Настройки", "⚙️ Settings", "Settings", 5),
                ]
            },
            {
                "slug": "settings", "name": "Settings",
                "message_text_ru": "⚙️ Настройки",
                "message_text_en": "⚙️ Settings",
                "is_system": True,
                "buttons": [
                    ("🌐 Язык", "🌐 Language", "Change_Language", 0),
                    ("📄 Пользовательское соглашение", "📄 User Agreement", "Agreement", 1),
                    ("🔒 Политика конфиденциальности", "🔒 Privacy Policy", "Privacy", 2),
                    ("◀️ На главную", "◀️ Main Menu", "Main", 3),
                ]
            },
        ]

        for screen_data in screens_data:
            screen = MenuScreen(
                slug=screen_data["slug"],
                name=screen_data["name"],
                message_text_ru=screen_data["message_text_ru"],
                message_text_en=screen_data["message_text_en"],
                is_system=screen_data["is_system"],
                is_active=True,
            )
            session.add(screen)
            await session.flush()

            for btn_data in screen_data["buttons"]:
                text_ru, text_en, callback, sort = btn_data[0], btn_data[1], btn_data[2], btn_data[3]
                button_type = btn_data[4] if len(btn_data) > 4 else "callback"
                session.add(MenuButton(
                    screen_id=screen.id, text_ru=text_ru, text_en=text_en,
                    callback_data=callback, row=sort, col=0, sort_order=sort,
                    button_type=button_type, is_active=True,
                ))

        await session.commit()
        logging.info("Seed: Telegram menu screens created")


async def _backfill_screen_texts():
    """Backfill empty message_text_ru/en for existing screens."""
    from sqlalchemy import select
    import app.locale.lang_ru as lang_ru
    import app.locale.lang_en as lang_en

    texts = {
        "main_new": {
            "ru": lang_ru.start_base + lang_ru.start_new + lang_ru.start_agreement,
            "en": lang_en.start_base + lang_en.start_new + lang_en.start_agreement,
        },
        "main_pro": {
            "ru": lang_ru.start_pro + "{sub_info}" + lang_ru.start_agreement,
            "en": lang_en.start_pro + "{sub_info}" + lang_en.start_agreement,
        },
        "main_free": {
            "ru": lang_ru.start_free + "{sub_info}" + lang_ru.start_agreement,
            "en": lang_en.start_free + "{sub_info}" + lang_en.start_agreement,
        },
        "settings": {
            "ru": "⚙️ Настройки",
            "en": "⚙️ Settings",
        },
    }

    async with async_session() as session:
        result = await session.execute(
            select(MenuScreen).where(MenuScreen.slug.in_(texts.keys()))
        )
        screens = result.scalars().all()
        updated = 0
        for screen in screens:
            t = texts.get(screen.slug)
            if not t:
                continue
            if not screen.message_text_ru:
                screen.message_text_ru = t["ru"]
                updated += 1
            if not screen.message_text_en:
                screen.message_text_en = t["en"]
                updated += 1
        if updated:
            await session.commit()
            logging.info("Backfill: updated %d screen text fields", updated)


async def _seed_telemt_free_params():
    """Ensure telemt_free_params has a default row."""
    from sqlalchemy import select, func
    async with async_session() as session:
        count = await session.scalar(select(func.count()).select_from(TelmtFreeParams))
        if not count:
            session.add(TelmtFreeParams(id=1, max_tcp_conns=None, max_unique_ips=None,
                                        data_quota_bytes=None, expire_days=30,
                                        rate_limit_up_bps=None, rate_limit_down_bps=None))
            await session.commit()
            logging.info("Seed: telemt_free_params default row created")


async def _seed_promo_settings():
    """Ensure promo_settings has a default row."""
    from sqlalchemy import select, func
    async with async_session() as session:
        count = await session.scalar(select(func.count()).select_from(PromoSettings))
        if not count:
            session.add(PromoSettings(id=1, default_discount_percent=20, default_credit_grant=100))
            await session.commit()
            logging.info("Seed: promo_settings default row created")


async def _seed_bot_feature_flags():
    """Ensure bot_feature_flags has a default row (legacy_bot_constructor=False)."""
    from sqlalchemy import select, func
    async with async_session() as session:
        count = await session.scalar(select(func.count()).select_from(BotFeatureFlags))
        if not count:
            session.add(BotFeatureFlags(id=1, legacy_bot_constructor=False))
            await session.commit()
            logging.info("Seed: bot_feature_flags default row created")
