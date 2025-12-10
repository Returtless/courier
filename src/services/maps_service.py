import requests
import json
import logging
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from src.config import settings
from src.models.order import Order
from src.database.connection import get_db_session

logger = logging.getLogger(__name__)

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
        self.two_gis_api_key = settings.two_gis_api_key
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Кэш для геокодирования (адрес -> (lat, lon, gis_id))
        self._geocode_cache: dict = {}
        
        # Кэш для маршрутов ((start_lat, start_lon, end_lat, end_lon) -> (distance, time))
        self._route_cache: dict = {}

    @staticmethod
    def build_route_links(
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        start_gis_id: Optional[str] = None,
        end_gis_id: Optional[str] = None,
        zoom: float = 15.8
    ) -> dict:
        """Сформировать ссылки на маршрут (2ГИС, Яндекс).
        Для 2ГИС используем format directions/points/... и, если есть, gid точек.
        """
        # 2ГИС: directions/points/lon,lat;gid|lon,lat;gid?m=center_lon,center_lat/zoom
        start_part = f"{start_lon}%2C{start_lat}" + (f"%3B{start_gis_id}" if start_gis_id else "")
        end_part = f"{end_lon}%2C{end_lat}" + (f"%3B{end_gis_id}" if end_gis_id else "")
        center_lon = (start_lon + end_lon) / 2
        center_lat = (start_lat + end_lat) / 2
        dg_route = (
            f"https://2gis.ru/spb/directions/points/"
            f"{start_part}%7C{end_part}?m={center_lon}%2C{center_lat}%2F{zoom}"
        )
        # Яндекс: rtext start~end
        return {
            "2gis": dg_route,
            "yandex": f"https://yandex.ru/maps/?rtext={start_lat},{start_lon}~{end_lat},{end_lon}&rtt=auto"
        }

    def build_point_links(self, lat: float, lon: float, gid: Optional[str] = None, zoom: float = 17.87) -> dict:
        """Сформировать ссылки на точку (2ГИС, Яндекс). Если есть gid (id 2ГИС), используем его."""
        if gid:
            dg_point = f"https://2gis.ru/geo/{gid}?m={lon}%2C{lat}%2F{zoom}"
        else:
            dg_point = f"https://2gis.ru/geo/{lat}%2C{lon}?m={lon}%2C{lat}%2F{zoom}"

        # Для Яндекса пытаемся получить house ID через геокодер
        yandex_point = self._get_yandex_house_link(lat, lon, zoom)

        return {
            "2gis": dg_point,
            "yandex": yandex_point
        }

    def _get_yandex_house_link(self, lat: float, lon: float, zoom: float = 17) -> str:
        """Получить ссылку на точку в Яндекс Картах через координаты"""
        # Используем простой формат с whatshere[point] - не требует геокодера
        return f"https://yandex.ru/maps/?whatshere[point]={lon},{lat}&whatshere[zoom]={int(zoom)}"

    async def __aenter__(self):
        if AIOHTTP_AVAILABLE:
            self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if AIOHTTP_AVAILABLE and self.session:
            await self.session.close()

    async def geocode_address(self, address: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """Получить координаты и id объекта (2ГИС) по адресу через 2GIS/Yandex (если нет) или fallback.
        Возвращает: lat, lon, gis_id
        """
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available, using sync geocoding")
            return self.geocode_address_sync(address)

        try:
            # 1) Попробуем 2GIS геокодирование
            if self.two_gis_api_key:
                url = "https://catalog.api.2gis.com/3.0/items"
                params = {
                    "key": self.two_gis_api_key,
                    "q": address,
                    "fields": "items.point"
                }
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        items = data.get("result", {}).get("items", [])
                        if items and items[0].get("point"):
                            point = items[0]["point"]
                            lat = float(point.get("lat"))
                            lon = float(point.get("lon"))
                            gid = items[0].get("id")
                            return lat, lon, gid

            # 2) Если есть ключ Яндекса — используем его
            if self.yandex_api_key:
                url = "https://geocode-maps.yandex.ru/1.x/"
                params = {
                    "apikey": self.yandex_api_key,
                    "format": "json",
                    "geocode": address
                }

                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        members = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
                        if members:
                            pos = members[0].get("GeoObject", {}).get("Point", {}).get("pos", "")
                            if pos:
                                lon, lat = map(float, pos.split())
                                return lat, lon, None
        except Exception as e:
            logger.warning(f"Async geocoding error: {e}")
            # Fallback to sync geocoding
            return self.geocode_address_sync(address)

        return self.geocode_address_sync(address)

    def geocode_address_sync(self, address: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """Синхронное геокодирование с fallback на 2GIS → Yandex → geopy. Возврат: lat, lon, gis_id"""
        # Нормализуем адрес для кэша
        address_key = address.lower().strip()
        
        # Проверяем in-memory кэш
        if address_key in self._geocode_cache:
            cached_result = self._geocode_cache[address_key]
            logger.debug(f"Геокодирование из памяти: {address}")
            return cached_result
        
        # Проверяем БД кэш
        try:
            from src.models.geocache import GeocodeCacheDB
            with get_db_session() as session:
                cached = session.query(GeocodeCacheDB).filter(
                    GeocodeCacheDB.address == address_key
                ).first()
                if cached:
                    result = (cached.latitude, cached.longitude, cached.gis_id)
                    # Сохраняем в in-memory кэш
                    self._geocode_cache[address_key] = result
                    logger.debug(f"Геокодирование из БД: {address}")
                    return result
        except Exception as e:
            logger.warning(f"Ошибка проверки БД кэша: {e}")
        
        # 1) 2GIS
        if self.two_gis_api_key:
            try:
                url = "https://catalog.api.2gis.com/3.0/items"
                params = {
                    "key": self.two_gis_api_key,
                    "q": address,
                    "fields": "items.point"
                }
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("result", {}).get("items", [])
                    if items and items[0].get("point"):
                        point = items[0]["point"]
                        lat = float(point.get("lat"))
                        lon = float(point.get("lon"))
                        gid = items[0].get("id")
                        result = (lat, lon, gid)
                        # Сохраняем в кэши
                        self._geocode_cache[address_key] = result
                        self._save_to_db_cache(address_key, lat, lon, gid)
                        return result
            except Exception as e:
                logger.warning(f"2GIS geocoding error: {e}")

        # 2) Yandex
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
                            result = (lat, lon, None)
                            # Сохраняем в кэши
                            self._geocode_cache[address_key] = result
                            self._save_to_db_cache(address_key, lat, lon, None)
                            return result
            except Exception as e:
                logger.warning(f"Yandex geocoding error: {e}")

        # Fallback to geopy
        if GEOPY_AVAILABLE:
            try:
                geolocator = Nominatim(user_agent="courier_bot")
                location = geolocator.geocode(address)
                if location:
                    result = (location.latitude, location.longitude, None)
                    # Сохраняем в кэши
                    self._geocode_cache[address_key] = result
                    self._save_to_db_cache(address_key, location.latitude, location.longitude, None)
                    return result
            except Exception as e:
                logger.warning(f"Geopy geocoding error: {e}")

        return None, None, None
    
    def _save_to_db_cache(self, address: str, lat: float, lon: float, gis_id: Optional[str]):
        """Сохранить результат геокодирования в БД кэш"""
        try:
            from src.models.geocache import GeocodeCacheDB
            with get_db_session() as session:
                # Проверяем, есть ли уже запись
                existing = session.query(GeocodeCacheDB).filter(
                    GeocodeCacheDB.address == address
                ).first()
                
                if existing:
                    # Обновляем существующую запись
                    existing.latitude = lat
                    existing.longitude = lon
                    existing.gis_id = gis_id
                    existing.updated_at = datetime.utcnow()
                else:
                    # Создаем новую запись
                    cache_entry = GeocodeCacheDB(
                        address=address,
                        latitude=lat,
                        longitude=lon,
                        gis_id=gis_id
                    )
                    session.add(cache_entry)
                session.commit()
        except Exception as e:
            # Не критично, если не удалось сохранить в БД кэш
            logger.warning(f"Не удалось сохранить в БД кэш: {e}")

    def get_route_sync(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> Tuple[float, float]:
        """Синхронный расчет маршрута через 2GIS (если есть ключ) с fallback."""
        # Проверяем кэш (округление координат до 5 знаков для ключа кэша)
        route_key = (
            round(start_lat, 5),
            round(start_lon, 5),
            round(end_lat, 5),
            round(end_lon, 5)
        )
        if route_key in self._route_cache:
            cached_result = self._route_cache[route_key]
            logger.debug(f"Маршрут из кэша: ({start_lat:.5f}, {start_lon:.5f}) -> ({end_lat:.5f}, {end_lon:.5f})")
            return cached_result
        
        # 1) 2GIS Routing API с учетом дорожной сети (traffic_mode=jam при наличии тарифа)
        if self.two_gis_api_key:
            try:
                # Используем версию 7.0.0, как в рабочем примере Postman
                url = "https://routing.api.2gis.com/routing/7.0.0/global"
                params = {"key": self.two_gis_api_key}
                payload_base = {
                    "points": [
                        {"type": "stop", "lon": start_lon, "lat": start_lat},
                        {"type": "stop", "lon": end_lon, "lat": end_lat},
                    ],
                    "locale": "ru",
                    "transport": "driving",
                    "route_mode": "fastest",
                }
                # Пробуем с пробками (jam). При 429 сразу уходим в fallback.
                payload = dict(payload_base, traffic_mode="jam")
                response = requests.post(url, params=params, json=payload, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    result = None
                    if isinstance(data, dict):
                        result = data.get("result")
                    elif isinstance(data, list) and data:
                        result = data[0].get("result")

                    if isinstance(result, list) and result:
                        route_obj = result[0]
                        distance = route_obj.get("total_distance", 0) / 1000  # метры → км
                        time_seconds = route_obj.get("total_duration", 0)  # секунды
                        time_minutes = time_seconds / 60
                        result_tuple = (distance, time_minutes)
                        # Сохраняем в кэш
                        self._route_cache[route_key] = result_tuple
                        return result_tuple
                elif response.status_code == 429:
                    logger.warning("2GIS route rate-limited (429), fallback to other providers")
                else:
                    try:
                        resp_text = response.text[:400]
                    except Exception:
                        resp_text = ""
                    logger.debug(f"2GIS route HTTP {response.status_code} (traffic_mode=jam): {resp_text}")
            except Exception as e:
                logger.warning(f"2GIS route error: {e}")

        # 2) Yandex (если есть ключ)
        if self.yandex_api_key:
            try:
                url = "https://api.routing.yandex.net/v2/route"
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
                        result_tuple = (distance, time_minutes)
                        # Сохраняем в кэш
                        self._route_cache[route_key] = result_tuple
                        return result_tuple

            except Exception as e:
                logger.warning(f"Yandex route error: {e}")

        # Fallback to distance calculation
        distance = self._calculate_distance(start_lat, start_lon, end_lat, end_lon)
        # Estimate time: 30 km/h average speed
        time_minutes = (distance / 30) * 60
        result_tuple = (distance, time_minutes)
        # Сохраняем в кэш (даже fallback результаты)
        self._route_cache[route_key] = result_tuple
        return result_tuple

    async def get_route_with_traffic(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float
    ) -> Tuple[float, float]:
        """
        Получить маршрут с учетом дорожной сети (2GIS) или fallback.
        Возвращает: (distance_km, time_minutes)
        """
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available, using sync routing")
            return self.get_route_sync(start_lat, start_lon, end_lat, end_lon)

        # 1) 2GIS при наличии ключа
        if self.two_gis_api_key:
            try:
                url = "https://routing.api.2gis.com/routing/7.0.0/global"
                params = {"key": self.two_gis_api_key}
                payload_base = {
                    "points": [
                        {"type": "stop", "lon": start_lon, "lat": start_lat},
                        {"type": "stop", "lon": end_lon, "lat": end_lat},
                    ],
                    "locale": "ru",
                    "transport": "driving",
                    "route_mode": "fastest",
                }
                payload = dict(payload_base, traffic_mode="jam")
                async with self.session.post(url, params=params, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = None
                        if isinstance(data, dict):
                            result = data.get("result")
                        elif isinstance(data, list) and data:
                            result = data[0].get("result")

                        if isinstance(result, list) and result:
                            route_obj = result[0]
                            distance = route_obj.get("total_distance", 0) / 1000
                            time_seconds = route_obj.get("total_duration", 0)
                            time_minutes = time_seconds / 60
                            return distance, time_minutes
                    elif response.status == 429:
                        logger.warning("Async 2GIS route rate-limited (429), fallback to other providers")
                    else:
                        text = ""
                        try:
                            text = (await response.text())[:400]
                        except Exception:
                            pass
                        logger.debug(f"Async 2GIS route HTTP {response.status} (traffic_mode=jam): {text}")
            except Exception as e:
                logger.warning(f"Async 2GIS route error: {e}")

        # 2) Yandex при наличии ключа
        if self.yandex_api_key:
            try:
                url = "https://api.routing.yandex.net/v2/route"
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
                logger.warning(f"Async route calculation error: {e}")
                return self.get_route_sync(start_lat, start_lon, end_lat, end_lon)

        # 3) Fallback
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
            logger.warning(f"Traffic info error: {e}")

        return {"level": 0, "description": "No traffic data"}
