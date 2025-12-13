from datetime import datetime, time, date
from typing import Optional, List
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Time, Date, JSON, Index
from pydantic import BaseModel
from src.database.connection import Base


class OrderDB(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # Telegram user ID
    order_date = Column(Date, nullable=False, index=True)  # Дата заказа
    customer_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    comment = Column(Text, nullable=True)
    delivery_time_start = Column(Time, nullable=True)
    delivery_time_end = Column(Time, nullable=True)
    delivery_time_window = Column(String, nullable=True)  # Строка формата "ЧЧ:ММ - ЧЧ:ММ"
    status = Column(String, default="pending")  # pending, assigned, delivered
    order_number = Column(String, nullable=True, index=True)  # Номер заказа из внешней системы
    entrance_number = Column(String, nullable=True)  # Номер подъезда
    apartment_number = Column(String, nullable=True)  # Номер квартиры
    gis_id = Column(String, nullable=True)  # ID объекта 2ГИС
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Route optimization fields
    estimated_delivery_time = Column(DateTime, nullable=True)
    call_time = Column(DateTime, nullable=True)
    route_order = Column(Integer, nullable=True)


class StartLocationDB(Base):
    __tablename__ = "start_locations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    location_date = Column(Date, nullable=False, index=True)
    location_type = Column(String, nullable=False)  # "geo" or "address"
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    start_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RouteDataDB(Base):
    __tablename__ = "route_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    route_date = Column(Date, nullable=False, index=True)
    route_summary = Column(JSON, nullable=True)  # Структурированные данные маршрута (список словарей) или список строк (старый формат)
    call_schedule = Column(JSON, nullable=True)  # Структурированные данные звонков (список словарей) или список строк (старый формат)
    route_order = Column(JSON, nullable=True)  # Порядок заказов в маршруте
    total_distance = Column(Float, nullable=True)
    total_time = Column(Float, nullable=True)
    estimated_completion = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CallStatusDB(Base):
    __tablename__ = "call_status"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    order_number = Column(String, nullable=False, index=True)
    call_date = Column(Date, nullable=False, index=True)
    call_time = Column(DateTime, nullable=False)  # Время когда нужно звонить
    phone = Column(String, nullable=False)
    customer_name = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, confirmed, rejected, failed (после 3 отклонений)
    attempts = Column(Integer, default=0)  # Количество попыток
    next_attempt_time = Column(DateTime, nullable=True)  # Время следующей попытки (через 2 минуты после отклонения)
    confirmation_comment = Column(Text, nullable=True)  # Комментарий при подтверждении
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_user_date', 'user_id', 'call_date'),
        Index('idx_status_time', 'status', 'call_time'),
    )


class UserSettingsDB(Base):
    """Персональные настройки пользователя"""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)  # Telegram user ID
    
    # Настройки времени для звонков
    call_advance_minutes = Column(Integer, default=10)  # За сколько минут до приезда звонить (по умолчанию 10)
    call_retry_interval_minutes = Column(Integer, default=2)  # Интервал между повторными попытками звонка
    call_max_attempts = Column(Integer, default=3)  # Максимальное количество попыток дозвона
    
    # Настройки времени доставки
    service_time_minutes = Column(Integer, default=10)  # Время нахождения на точке (по умолчанию 10 минут)
    parking_time_minutes = Column(Integer, default=7)  # Время на парковку и подход к подъезду
    
    # Настройки мониторинга пробок
    traffic_check_interval_minutes = Column(Integer, default=5)  # Интервал проверки пробок
    traffic_threshold_percent = Column(Integer, default=50)  # Процент увеличения времени для уведомления (по умолчанию 50%)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserSettings(BaseModel):
    """Pydantic модель для настроек пользователя"""
    user_id: int
    call_advance_minutes: int = 10
    call_retry_interval_minutes: int = 2
    call_max_attempts: int = 3
    service_time_minutes: int = 10
    parking_time_minutes: int = 7
    traffic_check_interval_minutes: int = 5
    traffic_threshold_percent: int = 50
    
    class Config:
        from_attributes = True


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
    apartment_number: Optional[str] = None  # Номер квартиры
    gis_id: Optional[str] = None  # ID объекта 2ГИС (для точного открытия точки)

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
