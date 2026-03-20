package com.courierplanning.routeopt.cluster

import com.courierplanning.routeopt.math.DeliveryTimeWindowParser
import com.courierplanning.routeopt.parity.ParityOptimizeJsonCodec
import com.courierplanning.routeopt.testsupport.loadAppTestResourceText
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.LocalTime
import java.time.ZonedDateTime

class ClusterParityTest {

    private fun hhmm(t: LocalTime?): String =
        t?.let { String.format(java.util.Locale.ROOT, "%02d:%02d", it.hour, it.minute) } ?: ""

    @Test
    fun tinyTwoOrders_clusterOrderMatchesPythonIntermediate() {
        val inputRaw = loadAppTestResourceText("parity_fixtures/tiny_two_orders/input.json")
        val expectedRaw = loadAppTestResourceText("parity_fixtures/tiny_two_orders/intermediate/cluster_orders.json")

        val input = ParityOptimizeJsonCodec.parseInput(inputRaw)
        val startZdt = ZonedDateTime.parse(input.startTimeIso)
        val zone = startZdt.zone
        val orderDate = startZdt.toLocalDate()

        val clusterOrders = input.orders.map { o ->
            ClusterSynchronizer.ClusterOrder(
                orderNumber = o.orderNumber,
                lat = o.lat,
                lon = o.lon,
                windowStart = o.windowStart?.let { DeliveryTimeWindowParser.parseExplicitHhMm(it) },
                windowEnd = o.windowEnd?.let { DeliveryTimeWindowParser.parseExplicitHhMm(it) },
            )
        }

        val actual = ClusterSynchronizer.clusterAndSynchronize(
            clusterOrders,
            orderDate,
            zone,
            input.startLocation.lat,
            input.startLocation.lon,
        )

        val expArr = JSONObject(expectedRaw).getJSONArray("orders_out")
        assertEquals("orders_out size", expArr.length(), actual.size)
        for (i in actual.indices) {
            val e = expArr.getJSONObject(i)
            val a = actual[i]
            assertEquals("order_number[$i]", e.getString("order_number"), a.orderNumber)
            assertEquals("window_start[$i]", e.optString("window_start", ""), hhmm(a.windowStart))
            assertEquals("window_end[$i]", e.optString("window_end", ""), hhmm(a.windowEnd))
            assertEquals("lat[$i]", e.getDouble("lat"), a.lat, 1e-9)
            assertEquals("lon[$i]", e.getDouble("lon"), a.lon, 1e-9)
        }
    }
}
