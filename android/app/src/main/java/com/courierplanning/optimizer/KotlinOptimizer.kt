package com.courierplanning.optimizer

import com.courierplanning.routeopt.math.Haversine
import com.courierplanning.routeopt.parity.LatLonJson
import com.courierplanning.routeopt.parity.MatrixCellJson
import com.courierplanning.routeopt.parity.ParityOptimizeInputJson
import com.courierplanning.routeopt.parity.ParityOptimizeJsonCodec
import com.courierplanning.routeopt.parity.ParityRouteFacade
import java.math.BigDecimal
import java.math.RoundingMode

/**
 * Drop-in replacement for Chaquopy [optimizer_bridge.optimize_route_json]: same JSON schema.
 * When `route_matrix` is empty, builds a full haversine matrix at 40 km/h (offline estimate, not live maps).
 */
object KotlinOptimizer {

    private const val SPEED_KMH = 40.0

    private fun round5(value: Double): Double =
        BigDecimal.valueOf(value).setScale(5, RoundingMode.HALF_EVEN).toDouble()

    fun optimizeRouteJson(payload: String): String {
        val input = ParityOptimizeJsonCodec.parseInput(payload)
        val withMatrix = if (input.routeMatrix.isEmpty()) {
            fillHaversineMatrix(input)
        } else {
            input
        }
        return ParityOptimizeJsonCodec.encodeOutput(ParityRouteFacade.optimize(withMatrix))
    }

    private fun fillHaversineMatrix(input: ParityOptimizeInputJson): ParityOptimizeInputJson {
        val nodes = mutableListOf(LatLonJson(input.startLocation.lat, input.startLocation.lon))
        for (o in input.orders) {
            nodes.add(LatLonJson(o.lat, o.lon))
        }
        val n = nodes.size
        val matrix = linkedMapOf<String, MatrixCellJson>()
        for (i in 0 until n) {
            for (j in 0 until n) {
                val key = "$i,$j"
                if (i == j) {
                    matrix[key] = MatrixCellJson(0.0, 0.0)
                } else {
                    val a = nodes[i]
                    val b = nodes[j]
                    val d = Haversine.distanceKm(a.lat, a.lon, b.lat, b.lon)
                    val t = (d / SPEED_KMH) * 60.0
                    matrix[key] = MatrixCellJson(round5(d), round5(t))
                }
            }
        }
        return input.copy(nodes = nodes, routeMatrix = matrix)
    }
}
