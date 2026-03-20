package com.courierplanning.routeopt.parity

import com.courierplanning.routeopt.testsupport.loadAppTestResourceText
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * End-to-end parity: same [input.json] as Python [tools.export_optimizer_golden], output must match [expected.json]
 * (excluding `meta`), using [ParityRouteFacade] (cluster/sync + Kotlin GA with [SplitMix64Rng], same hyperparameters as Python).
 */
class TinyTwoOrdersGoldenParityTest {

    @Test
    fun tinyTwoOrders_outputMatchesPythonGolden() {
        val inputRaw = loadAppTestResourceText("parity_fixtures/tiny_two_orders/input.json")
        val expectedRaw = loadAppTestResourceText("parity_fixtures/tiny_two_orders/expected.json")

        val input = ParityOptimizeJsonCodec.parseInput(inputRaw)
        val actual = ParityRouteFacade.optimize(input)

        val expObj = JSONObject(expectedRaw)
        expObj.remove("meta")
        val expected = ParityOptimizeJsonCodec.json.decodeFromString(
            ParityOptimizeOutputJson.serializer(),
            expObj.toString(),
        )

        assertEquals(expected.routePoints.size, actual.routePoints.size)
        expected.routePoints.zip(actual.routePoints).forEachIndexed { i, (e, a) ->
            assertEquals("point $i order_number", e.orderNumber, a.orderNumber)
            assertEquals("point $i estimated_arrival_iso", e.estimatedArrivalIso, a.estimatedArrivalIso)
            assertEquals("point $i distance", e.distanceFromPreviousKm, a.distanceFromPreviousKm, 1e-12)
            assertEquals("point $i travel_min", e.timeFromPreviousMin, a.timeFromPreviousMin, 1e-12)
            assertEquals("point $i is_late", e.isLate, a.isLate)
            assertEquals("point $i window_start", e.windowStart, a.windowStart)
            assertEquals("point $i window_end", e.windowEnd, a.windowEnd)
        }
        assertEquals("total_distance_km", expected.totalDistanceKm, actual.totalDistanceKm, 1e-12)
        assertEquals("total_time_min", expected.totalTimeMin, actual.totalTimeMin, 1e-12)
        assertEquals("estimated_completion_iso", expected.estimatedCompletionIso, actual.estimatedCompletionIso)
    }
}
