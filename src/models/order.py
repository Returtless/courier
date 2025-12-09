from datetime import datetime, time
from typing import Optional, List
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Time
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel

Base = declarative_base()


class OrderDB(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=True)
    phone = Column(String, nullable=False)
    address = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    comment = Column(Text, nullable=True)
    delivery_time_start = Column(Time, nullable=True)
    delivery_time_end = Column(Time, nullable=True)
    status = Column(String, default="pending")  # pending, assigned, delivered
    courier_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Route optimization fields
    estimated_delivery_time = Column(DateTime, nullable=True)
    call_time = Column(DateTime, nullable=True)
    route_order = Column(Integer, nullable=True)


class Order(BaseModel):
    id: Optional[int] = None
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    comment: Optional[str] = None
    delivery_time_start: Optional[time] = None
    delivery_time_end: Optional[time] = None
    status: str = "pending"
    courier_id: Optional[int] = None
    order_number: Optional[str] = None  # Номер заказа из внешней системы
    delivery_time_window: Optional[str] = None  # Временное окно доставки (строка)
    entrance_number: Optional[str] = None  # Номер подъезда для точного адреса

    def __init__(self, *args, **kwargs):
        # Поддержка позиционных аргументов для обратной совместимости
        if args:
            # customer_name, phone, address, comment
            if len(args) >= 1:
                kwargs['customer_name'] = args[0]
            if len(args) >= 2:
                kwargs['phone'] = args[1]
            if len(args) >= 3:
                kwargs['address'] = args[2]
            if len(args) >= 4:
                kwargs['comment'] = args[3]

        super().__init__(**kwargs)

        # Парсинг временного окна после инициализации
        if self.delivery_time_window:
            self._parse_time_window()

    def _parse_time_window(self):
        """Парсит строку временного окна в объекты time"""
        import re
        # Ищем паттерн ЧЧ:ММ - ЧЧ:ММ
        time_pattern = r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})'
        match = re.search(time_pattern, self.delivery_time_window)

        if match:
            start_hour, start_min, end_hour, end_min = map(int, match.groups())
            try:
                self.delivery_time_start = time(start_hour, start_min)
                self.delivery_time_end = time(end_hour, end_min)
            except ValueError:
                # Если время некорректное, оставляем None
                pass

    def get_time_window_minutes(self) -> tuple[int, int]:
        """Возвращает временное окно в минутах от начала дня"""
        if not self.delivery_time_start or not self.delivery_time_end:
            return (0, 24 * 60)  # Весь день по умолчанию

        start_minutes = self.delivery_time_start.hour * 60 + self.delivery_time_start.minute
        end_minutes = self.delivery_time_end.hour * 60 + self.delivery_time_end.minute

        return (start_minutes, end_minutes)

    class Config:
        from_attributes = True


class RoutePoint(BaseModel):
    order: Order
    estimated_arrival: datetime
    distance_from_previous: float = 0.0
    time_from_previous: float = 0.0  # minutes


class OptimizedRoute(BaseModel):
    points: List[RoutePoint]
    total_distance: float
    total_time: float  # minutes
    estimated_completion: datetime
