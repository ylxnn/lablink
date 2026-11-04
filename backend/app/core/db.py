from sqlalchemy import event
from sqlmodel import create_engine
from app.core.config import settings


def make_engine(url: str):
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False, "timeout": 20}
        if url.startswith("sqlite")
        else {},
    )
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def configure(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=20000")

    return engine


engine = make_engine(settings.DATABASE_URL)
