from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool
from config import settings
from loguru import logger


engine = create_engine(
    settings.database_url,
    poolclass=NullPool,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Run schema.sql to initialise all tables."""
    import os
    schema_path = os.path.join(os.path.dirname(__file__), "../../database/schema.sql")
    if not os.path.exists(schema_path):
        logger.warning("schema.sql not found at {}", schema_path)
        return
    with engine.connect() as conn:
        with open(schema_path) as f:
            conn.execute(text(f.read()))
        conn.commit()
    logger.info("Database schema initialised")
