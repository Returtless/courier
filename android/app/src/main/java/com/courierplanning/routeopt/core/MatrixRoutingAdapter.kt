package com.courierplanning.routeopt.core

/**
 * Abstraction for distance/travel time between coordinates (JSON matrix in tests, haversine or HTTP maps in prod).
 * Mirrors Python [tools.parity.fixture_maps_service.ParityMapsService.get_route_sync].
 */
fun interface MatrixRoutingAdapter {
    fun getRouteSync(
        startLat: Double,
        startLon: Double,
        endLat: Double,
        endLon: Double,
    ): Pair<Double, Double>
}
