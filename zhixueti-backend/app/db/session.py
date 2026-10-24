"""Database session and engine."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.sqltypes import BigInteger

from app.core.config import get_settings

settings = get_settings()

if settings.use_sqlite:

    @compiles(BigInteger, "sqlite")
    def _compile_bigint_sqlite(_type, _compiler, **_kw) -> str:
        # SQLite autoincrement requires INTEGER PRIMARY KEY
        return "INTEGER"


_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "echo": settings.debug,
}

if settings.use_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = settings.db_pool_size
    _engine_kwargs["max_overflow"] = settings.db_max_overflow
    _engine_kwargs["pool_recycle"] = 3600

engine = create_engine(settings.database_url, **_engine_kwargs)

if settings.use_sqlite:

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _connection_record) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
