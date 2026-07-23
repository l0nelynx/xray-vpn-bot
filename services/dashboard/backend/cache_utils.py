from common_db.repo.system import bump_cache_version as _bump_cache_version
from .database.session import async_session


async def bump_cache_version():
    """Increment cache_version so the bot picks up changes on next request."""
    async with async_session() as session:
        await _bump_cache_version(session)
        await session.commit()
