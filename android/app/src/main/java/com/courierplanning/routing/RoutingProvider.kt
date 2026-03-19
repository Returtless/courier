package com.courierplanning.routing

interface RoutingProvider {
    val name: String
    suspend fun getMetrics(from: LatLon, to: LatLon): RouteMetrics
}

interface GeocodingProvider {
    val name: String
    suspend fun geocode(address: String): GeocodeResult?
}

data class GeocodeResult(
    val lat: Double?,
    val lon: Double?,
    val gisId: String? = null,
)

