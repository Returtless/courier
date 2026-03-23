package com.courierplanning.optimizer

import com.courierplanning.maps.BotStyleRoutePrep
import com.courierplanning.maps.GeocodeCacheStore
import com.courierplanning.routeopt.math.Haversine
import com.courierplanning.routeopt.parity.LatLonJson
import com.courierplanning.routeopt.parity.MatrixCellJson
import com.courierplanning.routeopt.parity.ParityOptimizeInputJson
import com.courierplanning.routeopt.parity.ParityOptimizeJsonCodec
import com.courierplanning.routeopt.parity.ParityRouteFacade
import java.math.BigDecimal
import java.math.RoundingMode

/**
 * Полный путь как у бота: при непустых ключах карт — геокод + OSRM-матрица; иначе haversine (офлайн).
 */
object KotlinOptimizer {

    /** Как оценка жадного в Python: [GREEDY_EST_KM_PER_MIN]=0.5 → ~30 км/ч. */
    private const val SPEED_KMH = 30.0

    private fun round5(value: Double): Double =
        BigDecimal.valueOf(value).setScale(5, RoundingMode.HALF_EVEN).toDouble()

    /**
     * @param persistentGeocodeCache опционально Room/DataStore как [GeocodeCacheDB] в боте.
     * @param onGeocoded сохранить координаты и при необходимости `gis_id` 2GIS в заказ.
     */
    suspend fun optimizeRouteJson(
        payload: String,
        persistentGeocodeCache: GeocodeCacheStore? = null,
        onGeocoded: suspend (orderNumber: String, lat: Double, lon: Double, gisId: String?) -> Unit =
            { _, _, _, _ -> },
    ): String {
        val input = ParityOptimizeJsonCodec.parseInput(payload)
        val withMatrix = when {
            input.routeMatrix.isNotEmpty() -> input
            input.yandexApiKey.isNotBlank() || input.twoGisApiKey.isNotBlank() ->
                BotStyleRoutePrep.geocodeAndBuildMatrix(
                    input,
                    persistentGeocodeCache = persistentGeocodeCache,
                    onGeocoded = onGeocoded,
                )
            else -> fillHaversineMatrix(input)
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
