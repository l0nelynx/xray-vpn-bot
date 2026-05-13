from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .url import async_db_url

DB_URL = async_db_url(default_sqlite_path="/app/db.sqlite3")

_connect_args: dict = {}
if DB_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False, "timeout": 30}

engine = create_async_engine(
    DB_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)
