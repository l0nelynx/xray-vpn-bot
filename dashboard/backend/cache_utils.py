from sqlalchemy import update
from .database.models import CacheVersion
from .database.session import async_session


async def bump_cache_version():
    """Increment cache_version so the bot picks up changes on next request."""
    async with async_session() as session:
        await session.execute(
            update(CacheVersion)
            .where(CacheVersion.id == 1)
            .values(version=CacheVersion.version + 1)
        )
        await session.commit()
