from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sanolifood.soar.config import get_soar_settings


class SoarBase(DeclarativeBase):
    pass


database_url = get_soar_settings().soar_database_url
if database_url.startswith("sqlite"):
    soar_engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    soar_engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
    )
SoarSessionLocal = sessionmaker(bind=soar_engine, autoflush=False, expire_on_commit=False)


def get_soar_db() -> Generator[Session, None, None]:
    session = SoarSessionLocal()
    try:
        yield session
    finally:
        session.close()
