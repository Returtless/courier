package com.courierplanning.routeopt.parity

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
data class LatLonJson(
    @SerialName("lat")
    val lat: Double,
    @SerialName("lon")
    val lon: Double,
)

@Serializable
data class ServiceSettingsJson(
    @SerialName("service_time_minutes")
    val serviceTimeMinutes: Int = 10,
)

@Serializable
data class MatrixCellJson(
    @SerialName("distance_km")
    val distanceKm: Double,
    @SerialName("travel_min")
    val travelMin: Double,
)

@Serializable
data class ParityOrderJson(
    @SerialName("order_number")
    val orderNumber: String,
    @SerialName("address")
    val address: String = "",
    @SerialName("lat")
    val lat: Double,
    @SerialName("lon")
    val lon: Double,
    @SerialName("window_start")
    val windowStart: String? = null,
    @SerialName("window_end")
    val windowEnd: String? = null,
    @SerialName("manual_arrival_iso")
    val manualArrivalIso: String? = null,
)

@Serializable
data class ParityOptimizeInputJson(
    @SerialName("rng_seed")
    val rngSeed: Int = 42,
    @SerialName("start_location")
    val startLocation: LatLonJson,
    @SerialName("start_time_iso")
    val startTimeIso: String,
    @SerialName("settings")
    val settings: ServiceSettingsJson = ServiceSettingsJson(),
    @SerialName("nodes")
    val nodes: List<LatLonJson>,
    @SerialName("route_matrix")
    val routeMatrix: Map<String, MatrixCellJson>,
    @SerialName("orders")
    val orders: List<ParityOrderJson>,
)

@Serializable
data class RoutePointOutJson(
    @SerialName("order_number")
    val orderNumber: String,
    @SerialName("estimated_arrival_iso")
    val estimatedArrivalIso: String,
    @SerialName("distance_from_previous_km")
    val distanceFromPreviousKm: Double,
    @SerialName("time_from_previous_min")
    val timeFromPreviousMin: Double,
    @SerialName("is_late")
    val isLate: Boolean,
    @SerialName("window_start")
    val windowStart: String? = null,
    @SerialName("window_end")
    val windowEnd: String? = null,
)

@Serializable
data class ParityOptimizeOutputJson(
    @SerialName("route_points")
    val routePoints: List<RoutePointOutJson>,
    @SerialName("total_distance_km")
    val totalDistanceKm: Double,
    @SerialName("total_time_min")
    val totalTimeMin: Double,
    @SerialName("estimated_completion_iso")
    val estimatedCompletionIso: String,
)

object ParityOptimizeJsonCodec {
    val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        prettyPrint = false
    }

    fun parseInput(raw: String): ParityOptimizeInputJson = json.decodeFromString(raw)

    fun encodeOutput(out: ParityOptimizeOutputJson): String = json.encodeToString(ParityOptimizeOutputJson.serializer(), out)

    /** JSON in/out entrypoint for parity / future replacement of Chaquopy bridge. */
    fun optimizeRouteJson(payload: String): String {
        val input = parseInput(payload)
        val out = ParityRouteFacade.optimize(input)
        return encodeOutput(out)
    }
}
