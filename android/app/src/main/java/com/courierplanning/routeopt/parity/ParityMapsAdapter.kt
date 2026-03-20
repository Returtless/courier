package com.courierplanning.routeopt.parity

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * Mirrors [tools.parity.fixture_maps_service.ParityMapsService]: route legs from a JSON matrix, no network.
 *
 * @param nodes index 0 = start, then orders in the same order as the payload `orders` array.
 * @param matrix keys "i,j" with distance_km and travel_min
 */
class ParityMapsAdapter(
    nodes: List<Pair<Double, Double>>,
    private val matrix: Map<String, Leg>,
) {
    data class Leg(val distanceKm: Double, val travelMin: Double)

    private val coordToIdx: Map<Pair<Double, Double>, Int> =
        nodes.mapIndexed { i, p -> round5(p.first) to round5(p.second) to i }.associate { it.first to it.second }

    fun getRouteSync(
        startLat: Double,
        startLon: Double,
        endLat: Double,
        endLon: Double,
    ): Pair<Double, Double> {
        val i = coordToIdx[round5(startLat) to round5(startLon)]
            ?: error("Unknown start node ($startLat,$startLon) rounded (${round5(startLat)},${round5(startLon)})")
        val j = coordToIdx[round5(endLat) to round5(endLon)]
            ?: error("Unknown end node ($endLat,$endLon)")
        val key = "$i,$j"
        val leg = matrix[key] ?: error("Missing matrix key $key")
        return leg.distanceKm to leg.travelMin
    }

    companion object {
        /** Match Python 3 `round(x, 5)` (banker's rounding). */
        fun round5(value: Double): Double =
            BigDecimal.valueOf(value).setScale(5, RoundingMode.HALF_EVEN).toDouble()
    }
}
