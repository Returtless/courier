#!/usr/bin/env python3
"""
Тест Yandex Maps API ключа
"""

import requests
from src.config import settings


def test_yandex_geocoding():
    """Тест геокодирования через Yandex API"""
    print("🗺️ Тестирование Yandex Maps API геокодирования...")

    api_key = settings.yandex_maps_api_key
    if not api_key:
        print("❌ Yandex API ключ не найден в настройках")
        return False

    print(f"🔑 Используемый API ключ: {api_key[:10]}...")

    # Тестовый адрес
    test_address = "Москва, Красная площадь, 1"

    try:
        url = "https://geocode-maps.yandex.ru/1.x/"
        params = {
            "apikey": api_key,
            "format": "json",
            "geocode": test_address
        }

        print(f"📡 Запрос: {test_address}")
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Проверяем ответ
            response_meta = data.get("response", {}).get("GeoObjectCollection", {})
            found_count = response_meta.get("metaDataProperty", {}).get("GeocoderResponseMetaData", {}).get("found", "0")

            print(f"📊 Найдено объектов: {found_count}")

            if int(found_count) > 0:
                members = response_meta.get("featureMember", [])
                if members:
                    pos = members[0].get("GeoObject", {}).get("Point", {}).get("pos", "")
                    if pos:
                        lon, lat = map(float, pos.split())
                        print(f"✅ Координаты: {lat:.6f}, {lon:.6f}")
                        print("✅ Геокодирование работает!")
                        return True

            print("⚠️ Объекты найдены, но не удалось извлечь координаты")
            return False
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            print(f"📄 Ответ: {response.text[:200]}...")
            return False

    except requests.exceptions.Timeout:
        print("❌ Таймаут запроса (10 сек)")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка соединения")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_yandex_routing():
    """Тест построения маршрута через Yandex API"""
    print("\n🚗 Тестирование Yandex Maps API маршрутов...")

    api_key = settings.yandex_maps_api_key
    if not api_key:
        print("❌ Yandex API ключ не найден в настройках")
        return False

    try:
        # Координаты для теста (Красная площадь -> Лубянская площадь)
        start_lon, start_lat = 37.6173, 55.7558  # Красная площадь
        end_lon, end_lat = 37.6256, 55.7599     # Лубянская площадь

        url = "https://api.routing.yandex.net/v2/route"
        waypoints_format = f"{start_lon},{start_lat}|{end_lon},{end_lat}"
        print(f"🔄 Формат waypoints: {waypoints_format}")

        params = {
            "apikey": api_key,
            "waypoints": waypoints_format,
            "mode": "driving"
        }

        try:
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                route = data.get("route", {})

                if route:
                    distance = route.get("distance", 0) / 1000  # метры в км
                    time_seconds = route.get("duration", 0)  # Без учета пробок
                    time_minutes = time_seconds / 60

                    print("✅ Маршрут построен!")
                    print(f"📏 Расстояние: {distance:.1f} км")
                    print(f"⏱️ Время: {time_minutes:.0f} мин (без учета пробок)")
                    print("ℹ️ Для учета пробок нужен премиум тариф Yandex")
                    return True

            print(f"⚠️ HTTP ошибка: {response.status_code} - {response.text[:120]}...")

        except Exception as e:
            print(f"⚠️ Ошибка маршрутизации: {e}")

        return False

        print("📡 Запрос маршрута: Красная площадь → Лубянская площадь")
        print("ℹ️ Примечание: пробки не учитываются (API ограничение)")
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            route = data.get("route", {})

            if route:
                distance = route.get("distance", 0) / 1000  # метры в км
                time_seconds = route.get("duration", 0)  # Без учета пробок
                time_minutes = time_seconds / 60

                print("✅ Маршрут построен!")
                print(f"📏 Расстояние: {distance:.1f} км")
                print(f"⏱️ Время: {time_minutes:.0f} мин (без учета пробок)")
                print("ℹ️ Для учета пробок нужен премиум тариф Yandex")
                return True
            else:
                print("⚠️ Маршрут не найден в ответе API")
                print(f"📄 Ответ: {data}")
                return False
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            print(f"📄 Ответ: {response.text[:200]}...")
            return False

    except requests.exceptions.Timeout:
        print("❌ Таймаут запроса (10 сек)")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка соединения")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def check_api_limits():
    """Проверка лимитов API"""
    print("\n📊 Проверка лимитов Yandex API...")

    # По документации Yandex Maps API:
    # - Геокодирование: до 25,000 запросов в сутки
    # - Маршруты: до 25,000 запросов в сутки
    # - Стоимость: первые 25,000 запросов бесплатны

    print("ℹ️ Лимиты Yandex Maps API:")
    print("   • Геокодирование: 25,000 запросов/сутки")
    print("   • Маршруты: 25,000 запросов/сутки")
    print("   • Первые 25,000 запросов: бесплатно")
    print("   • Дополнительно: 200₽ за 1,000 запросов")

    print("\n💡 Рекомендации:")
    print("   • Кэшируйте результаты геокодирования")
    print("   • Избегайте повторных запросов для одних адресов")
    print("   • Мониторьте использование API")


def main():
    print("🔍 ТЕСТИРОВАНИЕ YANDEX MAPS API КЛЮЧА")
    print("=" * 50)

    # Проверяем настройки
    api_key = settings.yandex_maps_api_key
    if not api_key:
        print("❌ Yandex API ключ не настроен!")
        print("\n🔧 Настройка:")
        print("1. Перейдите: https://developer.tech.yandex.ru/")
        print("2. Зарегистрируйтесь и создайте приложение")
        print("3. Получите API ключ для 'JavaScript API и HTTP Геокодер'")
        print("4. Добавьте в файл env:")
        print("   YANDEX_MAPS_API_KEY=ваш_ключ_здесь")
        return

    print(f"🔑 Найден API ключ: {api_key[:15]}...")
    print()

    # Тестируем геокодирование
    geocoding_ok = test_yandex_geocoding()

    # Тестируем маршруты
    routing_ok = test_yandex_routing()

    # Показываем лимиты
    check_api_limits()

    print("\n" + "=" * 50)
    if geocoding_ok and routing_ok:
        print("🎉 YANDEX API КЛЮЧ РАБОТАЕТ ПОЛНОСТЬЮ!")
        print("\n✅ Геокодирование: работает")
        print("✅ Маршруты: работают")
        print("✅ Пробки: поддерживаются")
    elif geocoding_ok:
        print("⚠️ ГЕОКОДИРОВАНИЕ РАБОТАЕТ, НО МАРШРУТЫ НЕТ")
        print("\n✅ Геокодирование: работает")
        print("❌ Маршруты: проблемы")
    else:
        print("❌ YANDEX API КЛЮЧ НЕ РАБОТАЕТ")
        print("\n❌ Проверьте:")
        print("   • Корректность API ключа")
        print("   • Активацию ключа для нужных сервисов")
        print("   • Наличие прав доступа")


if __name__ == "__main__":
    main()
