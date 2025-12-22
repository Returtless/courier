"""
Форматтеры для отображения данных в Telegram
Инкапсулируют логику форматирования заказов, маршрутов и звонков
"""
import logging
from datetime import datetime, date, time
from typing import List, Dict, Optional, Tuple
from src.models.order import Order
from src.services.maps_service import MapsService
from src.constants.messages import Emojis
from src.database.connection import get_db_session
from src.models.order import CallStatusDB

logger = logging.getLogger(__name__)


class OrderFormatter:
    """Форматтер для заказов"""
    
    @staticmethod
    def format_order_details(order: Order, order_number: int = None) -> str:
        """
        Форматировать детали заказа для отображения
        
        Args:
            order: Объект заказа
            order_number: Порядковый номер заказа (опционально)
            
        Returns:
            Отформатированный текст заказа
        """
        lines = []
        
        # Заголовок
        if order_number:
            title = f"<b>{order_number}. Заказ №{order.order_number}</b>"
        else:
            title = f"<b>Заказ №{order.order_number}</b>"
        
        if order.customer_name:
            title += f" ({order.customer_name})"
        lines.append(title)
        
        # Адрес
        if order.address:
            lines.append(f"{Emojis.ADDRESS} {order.address}")
        else:
            lines.append(f"{Emojis.ADDRESS} Адрес не указан")
        
        # Контакты
        contact_parts = []
        if order.customer_name:
            contact_parts.append(f"{Emojis.USER} {order.customer_name}")
        if order.phone:
            contact_parts.append(f"{Emojis.PHONE} {order.phone}")
        
        if contact_parts:
            lines.append(" | ".join(contact_parts))
        elif not order.phone:
            lines.append(f"{Emojis.PHONE} Телефон не указан")
        
        # Время доставки
        if order.delivery_time_window:
            lines.append(f"{Emojis.CLOCK} {order.delivery_time_window}")
        
        # Детали доставки
        delivery_details = []
        if order.entrance_number:
            delivery_details.append(f"{Emojis.ENTRANCE} Подъезд {order.entrance_number}")
        if order.apartment_number:
            delivery_details.append(f"{Emojis.APARTMENT} Кв. {order.apartment_number}")
        
        if delivery_details:
            lines.append(" | ".join(delivery_details))
        
        # Комментарий
        if order.comment:
            lines.append(f"{Emojis.COMMENT} {order.comment}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_order_short(order: Order) -> str:
        """
        Форматировать краткую информацию о заказе
        
        Args:
            order: Объект заказа
            
        Returns:
            Краткий текст заказа
        """
        parts = []
        if order.order_number:
            parts.append(f"№{order.order_number}")
        if order.customer_name:
            parts.append(order.customer_name)
        if order.address:
            parts.append(order.address)
        
        return " | ".join(parts) if parts else "Заказ"


class RouteFormatter:
    """Форматтер для маршрутов"""
    
    def __init__(self, maps_service: MapsService):
        """
        Args:
            maps_service: Сервис для работы с картами
        """
        self.maps_service = maps_service
    
    def format_route_point(
        self,
        point_data: Dict,
        order: Order,
        order_index: int,
        call_time: datetime,
        call_status: Optional[str] = None,
        prev_latlon: Optional[Tuple[float, float]] = None,
        prev_gid: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Форматировать точку маршрута
        
        Args:
            point_data: Данные точки маршрута
            order: Объект заказа
            order_index: Порядковый номер заказа
            call_time: Время звонка
            call_status: Статус звонка (опционально)
            prev_latlon: Координаты предыдущей точки (опционально)
            prev_gid: GIS ID предыдущей точки (опционально)
            
        Returns:
            Словарь с ключами:
            - "text": отформатированный текст
            - "order_number": номер заказа
        """
        lines = []
        
        # Заголовок
        order_title = f"Заказ №{order.order_number}" if order.order_number else "Заказ"
        if order.customer_name:
            order_title += f" ({order.customer_name})"
        lines.append(f"<b>{order_index}. {order_title}</b>")
        
        # Адрес
        if order.address:
            lines.append(f"{Emojis.ADDRESS} {order.address}")
        else:
            lines.append(f"{Emojis.ADDRESS} Адрес не указан")
        
        # Контакты
        contact_parts = []
        if order.customer_name:
            contact_parts.append(f"{Emojis.USER} {order.customer_name}")
        if order.phone:
            contact_parts.append(f"{Emojis.PHONE} {order.phone}")
        
        if contact_parts:
            lines.append(" | ".join(contact_parts))
        elif not order.phone:
            lines.append(f"{Emojis.PHONE} Телефон не указан")
        
        # Время доставки и статус
        estimated_arrival = datetime.fromisoformat(point_data.get('estimated_arrival'))
        if order.delivery_time_window:
            arrival_status = ""
            if order.delivery_time_start and order.delivery_time_end:
                today_date = estimated_arrival.date()
                window_start = datetime.combine(today_date, order.delivery_time_start)
                window_end = datetime.combine(today_date, order.delivery_time_end)
                
                if estimated_arrival < window_start:
                    arrival_status = f" {Emojis.WARNING} Раньше окна"
                elif estimated_arrival > window_end:
                    arrival_status = f" {Emojis.WARNING} Позже окна"
                else:
                    arrival_status = f" {Emojis.CHECK}"
            
            lines.append(
                f"{Emojis.CLOCK} {order.delivery_time_window} | "
                f"Прибытие: {estimated_arrival.strftime('%H:%M')}{arrival_status}"
            )
        
        # Детали доставки
        delivery_details = []
        if order.entrance_number:
            delivery_details.append(f"{Emojis.ENTRANCE} Подъезд {order.entrance_number}")
        if order.apartment_number:
            delivery_details.append(f"{Emojis.APARTMENT} Кв. {order.apartment_number}")
        
        if delivery_details:
            lines.append(" | ".join(delivery_details))
        
        # Статус звонка
        if call_status == "failed":
            call_status_text = f"{Emojis.FAILED} НЕДОЗВОН"
        elif call_status == "confirmed":
            call_status_text = f"{Emojis.CHECK} Звонок: {call_time.strftime('%H:%M')}"
        else:
            call_status_text = f"{Emojis.PHONE} Звонок: {call_time.strftime('%H:%M')}"
        
        # Время звонка и маршрут
        route_info = [
            call_status_text,
            f"{Emojis.DISTANCE} {point_data.get('distance_from_previous', 0):.1f} км",
            f"{Emojis.DURATION} {point_data.get('time_from_previous', 0):.0f} мин"
        ]
        lines.append(" | ".join(route_info))
        
        # Ссылки на карты
        if order.latitude and order.longitude and prev_latlon:
            links = self.maps_service.build_route_links(
                prev_latlon[0],
                prev_latlon[1],
                order.latitude,
                order.longitude,
                prev_gid,
                order.gis_id
            )
            point_links = self.maps_service.build_point_links(
                order.latitude,
                order.longitude,
                order.gis_id
            )
            
            lines.append(
                f"{Emojis.LINK} <a href=\"{links['2gis']}\">Маршрут 2ГИС</a> | "
                f"<a href=\"{links['yandex']}\">Яндекс</a> | "
                f"<a href=\"{point_links['2gis']}\">Точка 2ГИС</a> | "
                f"<a href=\"{point_links['yandex']}\">Яндекс</a>"
            )
        
        # Комментарий
        if order.comment:
            lines.append(f"{Emojis.COMMENT} {order.comment}")
        
        return {
            "text": "\n".join(lines),
            "order_number": order.order_number
        }
    
    def format_route_summary(
        self,
        route_points_data: List[Dict],
        orders_dict: Dict[str, Dict],
        start_location_data: Dict,
        start_index: int = 1,
        prev_latlon: Optional[Tuple[float, float]] = None,
        prev_gid: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Форматировать полный маршрут
        
        Args:
            route_points_data: Список данных точек маршрута
            orders_dict: Словарь заказов (order_number -> order_data)
            start_location_data: Данные точки старта
            start_index: Начальный номер для нумерации (по умолчанию 1)
            prev_latlon: Координаты предыдущей точки (опционально)
            prev_gid: GIS ID предыдущей точки (опционально)
            
        Returns:
            Список словарей с ключами:
            - "text": отформатированный текст
            - "order_number": номер заказа
        """
        route_summary = []
        
        # Получаем координаты старта
        if prev_latlon is None:
            if start_location_data:
                if start_location_data.get('location_type') == 'geo':
                    prev_latlon = (
                        start_location_data.get('latitude'),
                        start_location_data.get('longitude')
                    )
                elif start_location_data.get('latitude') and start_location_data.get('longitude'):
                    prev_latlon = (
                        start_location_data.get('latitude'),
                        start_location_data.get('longitude')
                    )
        
        # Сортируем по времени прибытия
        try:
            sorted_points = sorted(
                route_points_data,
                key=lambda pd: datetime.fromisoformat(pd.get("estimated_arrival"))
            )
        except Exception as e:
            logger.error(f"Ошибка сортировки точек маршрута: {e}", exc_info=True)
            sorted_points = route_points_data
        
        for i, point_data in enumerate(sorted_points, start_index):
            order_number = point_data.get('order_number')
            if not order_number:
                continue
            
            order_data = orders_dict.get(order_number)
            if not order_data:
                continue
            
            # Пропускаем доставленные заказы
            if order_data.get('status', 'pending') == 'delivered':
                logger.debug(f"Пропускаем доставленный заказ {order_number} в маршруте")
                continue
            
            # Преобразуем данные заказа
            try:
                order = Order(**order_data)
            except Exception as e:
                logger.error(f"Ошибка создания Order из данных: {e}", exc_info=True)
                continue
            
            # Парсим время
            try:
                call_time = datetime.fromisoformat(point_data['call_time'])
            except Exception as e:
                logger.error(f"Ошибка парсинга времени: {e}", exc_info=True)
                continue
            
            # Получаем статус звонка
            call_status = None
            try:
                with get_db_session() as session:
                    call_status_obj = session.query(CallStatusDB).filter(
                        CallStatusDB.order_number == order_number,
                        CallStatusDB.call_date == date.today()
                    ).first()
                    if call_status_obj:
                        call_status = call_status_obj.status
            except Exception as e:
                logger.debug(f"Ошибка получения статуса звонка: {e}")
            
            # Форматируем точку
            point_text = self.format_route_point(
                point_data,
                order,
                i,
                call_time,
                call_status,
                prev_latlon,
                prev_gid
            )
            
            route_summary.append(point_text)
            
            # Обновляем prev_latlon для следующей точки
            if order.latitude and order.longitude:
                prev_latlon = (order.latitude, order.longitude)
                prev_gid = order.gis_id
        
        return route_summary
    
    @staticmethod
    def format_route_header(
        total_orders: int,
        total_distance: float,
        total_time: float,
        estimated_completion: datetime
    ) -> str:
        """
        Форматировать заголовок маршрута
        
        Args:
            total_orders: Общее количество заказов
            total_distance: Общее расстояние (км)
            total_time: Общее время (минуты)
            estimated_completion: Расчетное время завершения
            
        Returns:
            Отформатированный заголовок
        """
        return (
            f"{Emojis.CHECK} <b>Маршрут оптимизирован!</b>\n\n"
            f"{Emojis.PACKAGE} Всего заказов: {total_orders}\n"
            f"{Emojis.DISTANCE} Общее расстояние: {total_distance:.1f} км\n"
            f"{Emojis.DURATION} Общее время: {total_time:.0f} мин\n"
            f"{Emojis.COMPLETION} Завершение: {estimated_completion.strftime('%H:%M')}"
        )


class CallFormatter:
    """Форматтер для звонков"""
    
    @staticmethod
    def format_call_schedule_item(
        index: int,
        order_number: str,
        customer_name: Optional[str],
        phone: str,
        call_time: datetime,
        arrival_time: datetime,
        status: str = "pending"
    ) -> str:
        """
        Форматировать один элемент графика звонков
        
        Args:
            index: Порядковый номер
            order_number: Номер заказа
            customer_name: Имя клиента
            phone: Телефон
            call_time: Время звонка
            arrival_time: Время прибытия
            status: Статус звонка
            
        Returns:
            Отформатированный текст
        """
        # Определяем эмодзи статуса
        if status == "confirmed":
            status_emoji = Emojis.CHECK
        elif status == "failed":
            status_emoji = Emojis.FAILED
        else:
            status_emoji = Emojis.CLOCK
        
        text = f"{index}. {status_emoji} <b>№{order_number}</b>"
        if customer_name:
            text += f" ({customer_name})"
        text += f"\n   {Emojis.PHONE} {phone}\n"
        text += f"   {Emojis.CLOCK} Звонок: {call_time.strftime('%H:%M')}\n"
        text += f"   {Emojis.LOCATION} Прибытие: {arrival_time.strftime('%H:%M')}\n"
        
        return text
    
    @staticmethod
    def format_call_schedule(call_schedule: List[Dict], call_statuses: Dict[str, str] = None) -> str:
        """
        Форматировать полный график звонков
        
        Args:
            call_schedule: Список данных звонков
            call_statuses: Словарь статусов звонков (order_number -> status)
            
        Returns:
            Отформатированный текст графика
        """
        if call_statuses is None:
            call_statuses = {}
        
        text = f"<b>{Emojis.PHONE} График звонков</b>\n\n"
        
        for i, call_data in enumerate(call_schedule, 1):
            order_number = call_data.get('order_number', 'N/A')
            call_time = datetime.fromisoformat(call_data['call_time'])
            arrival_time = datetime.fromisoformat(call_data['arrival_time'])
            phone = call_data.get('phone', 'Не указан')
            customer_name = call_data.get('customer_name', '')
            status = call_statuses.get(order_number, 'pending')
            
            text += CallFormatter.format_call_schedule_item(
                i, order_number, customer_name, phone, call_time, arrival_time, status
            )
            text += "\n"
        
        return text
    
    @staticmethod
    def format_call_notification(
        order_number: str,
        customer_name: Optional[str],
        phone: str,
        call_time: datetime,
        is_retry: bool = False,
        attempts: int = 0
    ) -> str:
        """
        Форматировать уведомление о звонке
        
        Args:
            order_number: Номер заказа
            customer_name: Имя клиента
            phone: Телефон
            call_time: Время звонка
            is_retry: True если это повторная попытка
            attempts: Количество попыток
            
        Returns:
            Отформатированный текст уведомления
        """
        if is_retry:
            text = (
                f"{Emojis.PHONE} <b>Повторное уведомление!</b>\n\n"
                f"{Emojis.USER} {customer_name or 'Клиент'}\n"
                f"{Emojis.PACKAGE} Заказ №{order_number}\n"
                f"{Emojis.PHONE} {phone}\n"
                f"{Emojis.CLOCK} Время: {call_time.strftime('%H:%M')}\n"
                f"{Emojis.RETRY} Попытка: {attempts + 1}"
            )
        else:
            text = (
                f"{Emojis.PHONE} <b>Время звонка!</b>\n\n"
                f"{Emojis.USER} {customer_name or 'Клиент'}\n"
                f"{Emojis.PACKAGE} Заказ №{order_number}\n"
                f"{Emojis.PHONE} {phone}\n"
                f"{Emojis.CLOCK} Время: {call_time.strftime('%H:%M')}"
            )
        
        return text

