package com.courierplanning.routing

import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt

class HaversineRoutingProvider(
    private val kmPerMin: Double = 0.5, // ~30 km/h
) : RoutingProvider {
    override val name: String = "fallback"

    override suspend fun getMetrics(from: LatLon, to: LatLon): RouteMetrics {
        val km = haversineKm(from, to)
        val min = if (kmPerMin > 0) km / kmPerMin else km * 2
        return RouteMetrics(distanceKm = km, travelMin = min)
    }

    private fun haversineKm(a: LatLon, b: LatLon): Double {
        val r = 6371.0
        val dLat = Math.toRadians(b.lat - a.lat)
        val dLon = Math.toRadians(b.lon - a.lon)
        val lat1 = Math.toRadians(a.lat)
        val lat2 = Math.toRadians(b.lat)
        val h = sin(dLat / 2).pow(2.0) + cos(lat1) * cos(lat2) * sin(dLon / 2).pow(2.0)
        return 2 * r * atan2(sqrt(h), sqrt(1 - h))
    }
}

class StubGeocodingProvider(
    override val name: String = "stub",
) : GeocodingProvider {
    override suspend fun geocode(address: String): GeocodeResult? = null
}

