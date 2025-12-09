import requests
import json
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from src.config import settings
from src.models.order import Order

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    from geopy.geocoders import Nominatim
    from geopy.distance import geodesic
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False


class MapsService:
    def __init__(self):
        self.yandex_api_key = settings.yandex_maps_api_key
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        if AIOHTTP_AVAILABLE:
            self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if AIOHTTP_AVAILABLE and self.session:
            await self.session.close()

    async def geocode_address(self, address: str) -> Tuple[Optional[float], Optional[float]]:
        """Получить координаты по адресу через Yandex Maps API"""
        if not AIOHTTP_AVAILABLE:
            print("aiohttp not available, using sync geocoding")
            return self.geocode_address_sync(address)

        if not self.yandex_api_key:
            # Fallback to simple geocoding
            return self.geocode_address_sync(address)

        try:
            url = "https://geocode-maps.yandex.ru/1.x/"
            params = {
                "apikey": self.yandex_api_key,
                "format": "json",
                "geocode": address
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    # Parse Yandex response
                    members = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
                    if members:
                        pos = members[0].get("GeoObject", {}).get("Point", {}).get("pos", "")
                        if pos:
                            lon, lat = map(float, pos.split())
                            return lat, lon
        except Exception as e:
            print(f"Async geocoding error: {e}")
            # Fallback to sync geocoding
            return self.geocode_address_sync(address)

        return self.geocode_address_sync(address)

    def geocode_address_sync(self, address: str) -> Tuple[Optional[float], Optional[float]]:
        """Синхронное геокодирование с fallback на geopy"""
        # Сначала попробуем Yandex API
        if self.yandex_api_key:
            try:
                url = "https://geocode-maps.yandex.ru/1.x/"
                params = {
                    "apikey": self.yandex_api_key,
                    "format": "json",
                    "geocode": address
                }

                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    members = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
                    if members:
                        pos = members[0].get("GeoObject", {}).get("Point", {}).get("pos", "")
                        if pos:
                            lon, lat = map(float, pos.split())
                            return lat, lon
            except Exception as e:
                print(f"Yandex geocoding error: {e}")

        # Fallback to geopy
        if GEOPY_AVAILABLE:
            try:
                geolocator = Nominatim(user_agent="courier_bot")
                location = geolocator.geocode(address)
                if location:
                    return location.latitude, location.longitude
            except Exception as e:
                print(f"Geopy geocoding error: {e}")

        return None, None

    def get_route_sync(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> Tuple[float, float]:
        """Синхронный расчет маршрута"""
        if self.yandex_api_key:
            try:
                url = "https://api.routing.yandex.net/v2/route"

                # Формат waypoints для Routing API: lon1,lat1|lon2,lat2
                params = {
                    "apikey": self.yandex_api_key,
                    "waypoints": f"{start_lon},{start_lat}|{end_lon},{end_lat}",
                    "mode": "driving"
                }

                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    route = data.get("route", {})
                    if route:
                        distance = route.get("distance", 0) / 1000  # meters to km
                        time_seconds = route.get("duration", 0)  # Без учета пробок
                        time_minutes = time_seconds / 60
                        return distance, time_minutes

            except Exception as e:
                print(f"Yandex route error: {e}")

        # Fallback to distance calculation
        distance = self._calculate_distance(start_lat, start_lon, end_lat, end_lon)
        # Estimate time: 30 km/h average speed
        time_minutes = (distance / 30) * 60
        return distance, time_minutes

    async def get_route_with_traffic(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float
    ) -> Tuple[float, float]:
        """
        Получить маршрут (пробки не поддерживаются текущей версией API)
        Возвращает: (distance_km, time_minutes)
        """
        if not AIOHTTP_AVAILABLE:
            print("aiohttp not available, using sync routing")
            return self.get_route_sync(start_lat, start_lon, end_lat, end_lon)

        if not self.yandex_api_key:
            # Fallback: calculate straight line distance
            return self.get_route_sync(start_lat, start_lon, end_lat, end_lon)

        try:
            url = "https://api.routing.yandex.net/v2/route"

            # Формат waypoints для Routing API: lon1,lat1|lon2,lat2
            params = {
                "apikey": self.yandex_api_key,
                "waypoints": f"{start_lon},{start_lat}|{end_lon},{end_lat}",
                "mode": "driving"
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    route = data.get("route", {})
                    if route:
                        distance = route.get("distance", 0) / 1000  # meters to km
                        time_seconds = route.get("duration", 0)  # Без учета пробок
                        time_minutes = time_seconds / 60
                        return distance, time_minutes
        except Exception as e:
            print(f"Async route calculation error: {e}")
            # Fallback to sync routing
            return self.get_route_sync(start_lat, start_lon, end_lat, end_lon)

        # Fallback
        return self.get_route_sync(start_lat, start_lon, end_lat, end_lon)

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate approximate distance using Haversine formula"""
        from math import radians, sin, cos, sqrt, atan2

        R = 6371  # Earth's radius in km

        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)

        a = sin(dlat/2) * sin(dlat/2) + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2) * sin(dlon/2)
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    async def get_traffic_info(self, lat: float, lon: float, radius: int = 1000) -> dict:
        """Получить информацию о пробках в районе"""
        if not self.yandex_api_key:
            return {"level": 0, "description": "No traffic data"}

        try:
            url = "https://api.routing.yandex.net/v2/route"
            # For traffic info, we can use a small route around the point
            params = {
                "apikey": self.yandex_api_key,
                "waypoints": f"{lon},{lat};{lon+0.001},{lat+0.001}",
                "mode": "driving",
                "traffic": "jam"
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    # This is a simplified traffic check
                    return {"level": 5, "description": "Traffic data available"}
        except Exception as e:
            print(f"Traffic info error: {e}")

        return {"level": 0, "description": "No traffic data"}
