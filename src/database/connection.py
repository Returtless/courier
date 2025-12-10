from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from src.config import settings

# Поддержка SQLite и PostgreSQL
database_url = settings.database_url
if "sqlite" in database_url:
    connect_args = {"check_same_thread": False}
    engine = create_engine(database_url, connect_args=connect_args)
else:
    # PostgreSQL
    engine = create_engine(database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Генератор для FastAPI-style dependency injection"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """Контекстный менеджер для работы с БД"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
