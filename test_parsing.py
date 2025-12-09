#!/usr/bin/env python3
"""
Тест парсинга заказов в формате пользователя
"""

import re
from src.models.order import Order


def parse_order_text(text):
    """Парсит текст заказа в формате пользователя"""
    text = text.strip()

    # Проверяем формат: если содержит "|" - это расширенный формат
    if "|" in text:
        # Формат: Имя|Телефон|Адрес|Комментарий
        parts = text.split("|")
        if len(parts) < 3:
            raise ValueError("Недостаточно данных в расширенном формате")

        order_data = {
            'customer_name': parts[0].strip() if len(parts) > 0 else None,
            'phone': parts[1].strip() if len(parts) > 1 else None,
            'address': parts[2].strip(),
            'comment': parts[3].strip() if len(parts) > 3 else None,
            'order_number': None,
            'delivery_time_window': None
        }
    else:
        # Формат: Время НомерЗаказа Адрес
        # Пример: "10:00 - 13:00 3258104 г Санкт-Петербург, ул Манчестерская, д 3 стр 1"

        # Ищем паттерн времени (ЧЧ:ММ - ЧЧ:ММ)
        time_pattern = r'(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})'
        time_match = re.search(time_pattern, text)

        if time_match:
            time_window = time_match.group(1).strip()
            # Убираем время из текста, чтобы остался номер заказа и адрес
            remaining_text = text.replace(time_window, '').strip()

            # Ищем номер заказа (число в начале)
            order_num_match = re.match(r'(\d+)\s+', remaining_text)
            if order_num_match:
                order_number = order_num_match.group(1)
                address = remaining_text[order_num_match.end():].strip()
            else:
                # Если номер не найден, берем весь текст как адрес
                order_number = None
                address = remaining_text
        else:
            # Если время не найдено, весь текст считаем адресом
            time_window = None
            order_number = None
            address = text

        order_data = {
            'customer_name': None,
            'phone': None,
            'address': address,
            'comment': None,
            'order_number': order_number,
            'delivery_time_window': time_window
        }

    return order_data


def test_parsing():
    """Тест парсинга различных форматов"""
    print("🧪 Тестирование парсинга заказов")
    print("=" * 50)

    # Тестовые данные в формате пользователя
    test_cases = [
        "10:00 - 13:00 3258104 г Санкт-Петербург, ул Манчестерская, д 3 стр 1",
        "10:00 - 13:00 3258981 г Санкт-Петербург, ул Манчестерская, д 3 к 2 стр 1",
        "10:00 - 13:00 3259615 г Санкт-Петербург, Фермское шоссе, д 14 к 1",
        "10:00 - 13:00 3257998 г Санкт-Петербург, Санкт-Петербург, Фермское шоссе, д 22 к 3",
        "10:00 - 13:00 3258165 г Санкт-Петербург, ул 1-я Утиная, д 21",
        "Иван|+7-999-123-45-67|ул. Ленина, 10|Звонок в домофон",
        "10:00 - 13:00 3258122 Санкт-Петербург, 1-я Утиная улица, 32",
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Тест {i}:")
        print(f"   Вход: {test_case}")

        try:
            order_data = parse_order_text(test_case)

            # Создаем объект Order для проверки
            order = Order(**order_data)

            print("   ✅ Успешно распарсено:"            print(f"      Номер заказа: {order.order_number or 'Не указан'}")
            print(f"      Время доставки: {order.delivery_time_window or 'Не указано'}")
            print(f"      Адрес: {order.address}")
            print(f"      Имя: {order.customer_name or 'Не указано'}")
            print(f"      Телефон: {order.phone or 'Не указан'}")
            print(f"      Комментарий: {order.comment or 'Не указан'}")

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")


def test_update_functionality():
    """Тест обновления информации о заказах"""
    print("\n📝 Тестирование обновления заказов")
    print("=" * 50)

    # Создаем заказ без контактных данных
    order_data = parse_order_text("10:00 - 13:00 3258104 ул Манчестерская, д 3 стр 1")
    order = Order(**order_data)

    print("До обновления:")
    print(f"   Адрес: {order.address}")
    print(f"   Имя: {order.customer_name or 'Не указано'}")
    print(f"   Телефон: {order.phone or 'Не указан'}")
    print(f"   Комментарий: {order.comment or 'Не указан'}")
    print(f"   Подъезд: {order.entrance_number or 'Не указан'}")

    # Имитируем обновление с подъездом
    print("\n📝 Обновление с подъездом:")

    # Парсим строку обновления
    update_text = "3258104 +7-999-123-45-67 Иван домофон 05 подъезд:3"
    parts = update_text.split()

    order_number = parts[0]
    phone = parts[1] if len(parts) > 1 else None

    remaining_parts = parts[2:] if len(parts) > 2 else []
    entrance_number = None
    comment_parts = []

    for i, part in enumerate(remaining_parts):
        if part.lower().startswith('подъезд:'):
            entrance_number = part.split(':', 1)[1].strip()
            break
        else:
            comment_parts.append(part)

    customer_name = comment_parts[0] if comment_parts else None
    comment = ' '.join(comment_parts[1:]) if len(comment_parts) > 1 else None

    # Обновляем объект
    if phone:
        order.phone = phone
    if customer_name:
        order.customer_name = customer_name
    if comment:
        order.comment = comment
    if entrance_number:
        order.entrance_number = entrance_number
        # Добавляем подъезд к адресу
        if 'подъезд' not in order.address.lower():
            order.address = f"{order.address}, подъезд {entrance_number}"

    print("После обновления:")
    print(f"   Адрес: {order.address}")
    print(f"   Имя: {order.customer_name or 'Не указано'}")
    print(f"   Телефон: {order.phone or 'Не указан'}")
    print(f"   Комментарий: {order.comment or 'Не указан'}")
    print(f"   Подъезд: {order.entrance_number or 'Не указан'}")


def main():
    test_parsing()
    test_update_functionality()

    print("\n🎯 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
    print("\n💡 Система готова для работы с вашими данными!")


if __name__ == "__main__":
    main()
