from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Index
from src.database.connection import Base


class GeocodeCacheDB(Base):
    """Кэш для результатов геокодирования"""
    __tablename__ = "geocode_cache"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String, nullable=False, index=True)  # Нормализованный адрес (lower, strip)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    gis_id = Column(String, nullable=True)  # ID объекта 2ГИС
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_address', 'address'),
    )

