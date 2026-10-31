from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.errors import unavailable


def session_factory(settings: Settings):
    if not settings.database_url:
        unavailable("Database")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    return sessionmaker(engine, expire_on_commit=False)
