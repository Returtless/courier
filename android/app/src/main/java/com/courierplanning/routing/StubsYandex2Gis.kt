package com.courierplanning.routing

/**
 * Stubs for future integration with Yandex/2GIS APIs.
 * For now they throw so it's obvious if used without implementation.
 */
class YandexRoutingProvider : RoutingProvider {
    override val name: String = "yandex"
    override suspend fun getMetrics(from: LatLon, to: LatLon): RouteMetrics {
        throw NotImplementedError("Yandex routing is not implemented yet")
    }
}

class TwoGisRoutingProvider : RoutingProvider {
    override val name: String = "2gis"
    override suspend fun getMetrics(from: LatLon, to: LatLon): RouteMetrics {
        throw NotImplementedError("2GIS routing is not implemented yet")
    }
}

class YandexGeocodingProvider : GeocodingProvider {
    override val name: String = "yandex"
    override suspend fun geocode(address: String): GeocodeResult? {
        throw NotImplementedError("Yandex geocoding is not implemented yet")
    }
}

class TwoGisGeocodingProvider : GeocodingProvider {
    override val name: String = "2gis"
    override suspend fun geocode(address: String): GeocodeResult? {
        throw NotImplementedError("2GIS geocoding is not implemented yet")
    }
}

