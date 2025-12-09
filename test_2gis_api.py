#!/usr/bin/env python3
"""
Быстрый тест 2GIS API (геокодер + маршрутизация)
"""

import requests
from src.config import settings


def test_geocode_2gis():
    print("🗺️ Тест 2GIS геокодирования...")
    api_key = settings.two_gis_api_key
    if not api_key:
        print("❌ TWO_GIS_API_KEY не задан")
        return False

    address = "Санкт-Петербург, Манчестерская улица, 3"
    url = "https://catalog.api.2gis.com/3.0/items"
    params = {
        "key": api_key,
        "q": address,
        "fields": "items.point"
    }

    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code != 200:
        print(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")
        return False

    data = resp.json()
    items = data.get("result", {}).get("items", [])
    if not items or not items[0].get("point"):
        print("⚠️ Не удалось получить координаты")
        return False

    point = items[0]["point"]
    lat, lon = float(point["lat"]), float(point["lon"])
    print(f"✅ Координаты: {lat:.6f}, {lon:.6f}")
    return True


def test_route_2gis():
    print("\n🚗 Тест 2GIS маршрута...")
    api_key = settings.two_gis_api_key
    if not api_key:
        print("❌ TWO_GIS_API_KEY не задан")
        return False

    # Пример: Красная площадь -> Лубянская площадь
    start_lon, start_lat = 37.6173, 55.7558
    end_lon, end_lat = 37.6256, 55.7599

    url = "https://routing.api.2gis.com/routing/7.0.0/global"
    params = {"key": api_key}
    payload_base = {
        "points": [
            {"type": "stop", "lon": start_lon, "lat": start_lat},
            {"type": "stop", "lon": end_lon, "lat": end_lat},
        ],
        "locale": "ru",
        "transport": "driving",
        "route_mode": "fastest",
    }

    # Тестируем только с traffic_mode="jam"
    payload = dict(payload_base)
    payload["traffic_mode"] = "jam"
    resp = requests.post(url, params=params, json=payload, timeout=10)

    if resp.status_code == 200:
        data = resp.json()
    else:
        data = None

    # Ответ может быть dict с result или списком
    result = None
    if isinstance(data, dict):
        result = data.get("result")
    elif isinstance(data, list) and data:
        result = data[0].get("result")

    if isinstance(result, list) and result:
        route_obj = result[0]
        distance_km = route_obj.get("total_distance", 0) / 1000
        time_minutes = route_obj.get("total_duration", 0) / 60

        # Если нет total_distance, пробуем legs
        if distance_km == 0 and time_minutes == 0:
            legs = route_obj.get("legs", [])
            if legs:
                leg = legs[0]
                distance_km = leg.get("distance", {}).get("value", 0) / 1000
                time_minutes = leg.get("duration", {}).get("value", 0) / 60

        print("✅ Маршрут построен!")
        print(f"📏 Расстояние: {distance_km:.1f} км")
        print(f"⏱️ Время: {time_minutes:.0f} мин")
        return True

    print(f"⚠️ HTTP {resp.status_code}: {resp.text[:400]}")
    print("❌ Маршрут не найден")
    return False


def main():
    print("🔍 ТЕСТ 2GIS API")
    print("=" * 50)

    geocode_ok = test_geocode_2gis()
    route_ok = test_route_2gis()

    print("\n" + "=" * 50)
    if geocode_ok and route_ok:
        print("🎉 2GIS API работает!")
    elif geocode_ok:
        print("⚠️ Геокод работает, маршрут — нет")
    else:
        print("❌ Проблемы с 2GIS API")


if __name__ == "__main__":
    main()

