from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .url import async_db_url

DB_URL = async_db_url(default_sqlite_path="/app/db.sqlite3")

_connect_args: dict = {}
_pool_kwargs: dict = {}
if DB_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False, "timeout": 30}
else:
    # SQLAlchemy's asyncpg default is pool_size=5 + max_overflow=10 (15 max).
    # Bump it so a burst of concurrent Android/web requests doesn't start
    # queuing for a connection before CPU/memory are anywhere near their
    # limits. pool_size/max_overflow are QueuePool-only kwargs — sqlite uses a
    # different poolclass, hence the branch.
    _pool_kwargs = {"pool_size": 10, "max_overflow": 10}

engine = create_async_engine(
    DB_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
    **_pool_kwargs,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)
