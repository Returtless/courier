#!/usr/bin/env python3
"""
Демонстрация системы оптимизации маршрутов доставки
Консольная версия без сложных зависимостей
"""

from datetime import datetime, timedelta
from typing import List, Tuple
import json


class Order:
    def __init__(self, customer_name: str, phone: str, address: str, comment: str = None):
        self.customer_name = customer_name
        self.phone = phone
        self.address = address
        self.comment = comment
        self.latitude = None
        self.longitude = None

    def __str__(self):
        return f"{self.customer_name} - {self.address} ({self.phone})"


class RouteOptimizer:
    def __init__(self):
        self.delivery_time_per_stop = 10  # minutes
        self.call_advance_time = 40  # minutes before delivery

    def optimize_route(self, orders: List[Order], start_location: Tuple[float, float],
                      start_time: datetime) -> dict:
        """
        Простая оптимизация маршрутов (демонстрационная версия)
        """
        print("🔄 Оптимизирую маршрут...")

        # Имитация геокодирования
        for i, order in enumerate(orders):
            # Простая имитация координат
            order.latitude = 55.75 + (i * 0.01)  # Moscow area
            order.longitude = 37.61 + (i * 0.01)

        # Простая оптимизация: сортировка по расстоянию от старта
        optimized_orders = self._sort_by_distance(orders, start_location)

        # Расчет времени прибытия
        route_points = []
        current_time = start_time

        for i, order in enumerate(optimized_orders, 1):
            # Имитация времени в пути
            travel_time = 15 + (i * 5)  # minutes
            current_time += timedelta(minutes=travel_time + self.delivery_time_per_stop)

            route_points.append({
                'order': order,
                'estimated_arrival': current_time,
                'travel_time': travel_time,
                'stop_number': i
            })

        total_distance = sum(15 + (i * 5) for i in range(len(orders)))
        total_time = (current_time - start_time).total_seconds() / 60

        return {
            'points': route_points,
            'total_distance': total_distance,
            'total_time': total_time,
            'completion_time': current_time
        }

    def _sort_by_distance(self, orders: List[Order], start_location: Tuple[float, float]) -> List[Order]:
        """Простая сортировка по расстоянию (евклидово расстояние)"""
        def distance(order):
            if order.latitude and order.longitude:
                return ((order.latitude - start_location[0]) ** 2 +
                       (order.longitude - start_location[1]) ** 2) ** 0.5
            return float('inf')

        return sorted(orders, key=distance)


class CallScheduler:
    def __init__(self):
        self.call_advance_time = 40  # minutes

    def generate_call_schedule(self, route_result: dict) -> List[dict]:
        """Генерация графика звонков"""
        schedule = []

        for point in route_result['points']:
            order = point['order']
            delivery_time = point['estimated_arrival']

            # Звонок минимум за 40 минут до доставки
            call_time = delivery_time - timedelta(minutes=self.call_advance_time)

            # Анализ комментария для определения приоритета
            priority = self._analyze_priority(order.comment)

            schedule.append({
                'time': call_time,
                'customer': order.customer_name,
                'phone': order.phone,
                'address': order.address,
                'priority': priority,
                'delivery_time': delivery_time
            })

        return sorted(schedule, key=lambda x: x['time'])

    def _analyze_priority(self, comment: str) -> str:
        """Простой анализ приоритета на основе комментария"""
        if not comment:
            return "normal"

        comment_lower = comment.lower()
        if any(word in comment_lower for word in ['срочно', 'urgent', 'быстрее', 'fast']):
            return "high"
        elif any(word in comment_lower for word in ['время', 'точное', 'точно']):
            return "high"
        else:
            return "normal"


def main():
    print("🚚 Система оптимизации маршрутов доставки")
    print("=" * 50)

    # Создание тестовых заказов
    orders = [
        Order("Иван Петров", "+7-999-123-45-67", "ул. Ленина, д.10", "Звонок в домофон, срочно"),
        Order("Анна Сидорова", "+7-999-234-56-78", "пр. Победы, д.25", "Оставить у двери"),
        Order("Михаил Иванов", "+7-999-345-67-89", "ул. Гагарина, д.5", "Подъезд 3, код 1234"),
        Order("Елена Козлова", "+7-999-456-78-90", "ул. Пушкина, д.15", "Точное время, пожалуйста"),
    ]

    print(f"📦 Загружено {len(orders)} заказов:")
    for i, order in enumerate(orders, 1):
        print(f"  {i}. {order}")
        if order.comment:
            print(f"     💬 {order.comment}")
    print()

    # Параметры маршрута
    start_location = (55.7558, 37.6173)  # Красная площадь, Москва
    start_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    print(f"🏭 Точка старта: Москва, Красная площадь")
    print(f"🕐 Время старта: {start_time.strftime('%H:%M')}")
    print()

    # Оптимизация маршрута
    optimizer = RouteOptimizer()
    route_result = optimizer.optimize_route(orders, start_location, start_time)

    # Вывод результатов оптимизации
    print("✅ МАРШРУТ ОПТИМИЗИРОВАН")
    print("-" * 50)
    print(f"📊 Всего заказов: {len(route_result['points'])}")
    print(f"📏 Общее расстояние: ~{route_result['total_distance']:.1f} км")
    print(f"⏱️ Общее время: ~{route_result['total_time']:.0f} мин")
    print(f"🏁 Завершение: {route_result['completion_time'].strftime('%H:%M')}")
    print()

    print("🚚 ОПТИМАЛЬНЫЙ МАРШРУТ:")
    print("-" * 50)
    for point in route_result['points']:
        order = point['order']
        arrival = point['estimated_arrival']
        print(f"{point['stop_number']}. {order.customer_name}")
        print(f"   📍 {order.address}")
        print(f"   📞 {order.phone}")
        print(f"   ⏰ Прибытие: {arrival.strftime('%H:%M')}")
        if order.comment:
            print(f"   💬 {order.comment}")
        print()

    # Генерация графика звонков
    scheduler = CallScheduler()
    call_schedule = scheduler.generate_call_schedule(route_result)

    print("📞 ГРАФИК ЗВОНКОВ КЛИЕНТАМ:")
    print("-" * 50)
    for call in call_schedule:
        priority_emoji = "🔴" if call['priority'] == "high" else "🟡" if call['priority'] == "normal" else "🟢"
        print(f"{priority_emoji} {call['time'].strftime('%H:%M')} - {call['customer']} ({call['phone']})")
        print(f"   🚚 Доставка в {call['delivery_time'].strftime('%H:%M')}")
        print()

    # Сохранение результатов в JSON
    result_data = {
        'orders_count': len(orders),
        'total_distance': route_result['total_distance'],
        'total_time': route_result['total_time'],
        'route': [
            {
                'stop': point['stop_number'],
                'customer': point['order'].customer_name,
                'address': point['order'].address,
                'phone': point['order'].phone,
                'arrival_time': point['estimated_arrival'].isoformat(),
                'comment': point['order'].comment
            }
            for point in route_result['points']
        ],
        'call_schedule': [
            {
                'call_time': call['time'].isoformat(),
                'delivery_time': call['delivery_time'].isoformat(),
                'customer': call['customer'],
                'phone': call['phone'],
                'priority': call['priority']
            }
            for call in call_schedule
        ]
    }

    with open('route_result.json', 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print("💾 Результаты сохранены в route_result.json")

    print("\n🎯 СИСТЕМА ГОТОВА К ИСПОЛЬЗОВАНИЮ!")
    print("Для реального использования добавьте:")
    print("- 🤖 Telegram Bot API для интерфейса")
    print("- 🗺️ Yandex Maps API для реальных маршрутов")
    print("- 🧠 Gemma3-4B для анализа комментариев")
    print("- 🗄️ Базу данных для хранения заказов")


if __name__ == "__main__":
    main()

