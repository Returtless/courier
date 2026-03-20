package com.courierplanning.routing

data class LatLon(val lat: Double, val lon: Double) {
    fun key(precision: Int = 5): String {
        fun r(x: Double) = "%.${precision}f".format(x)
        return "${r(lat)},${r(lon)}"
    }
}

data class RouteMetrics(
    val distanceKm: Double,
    val travelMin: Double,
)

