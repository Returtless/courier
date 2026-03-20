package com.courierplanning.routeopt.parity

import com.courierplanning.routeopt.testsupport.loadAppTestResourceText
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

class ParityMapsAdapterTest {

    @Test
    fun matrixLookup_matchesFixture() {
        val json = loadAppTestResourceText("parity_fixtures/tiny_two_orders/input.json")
        val root = JSONObject(json)
        val nodesArr = root.getJSONArray("nodes")
        val nodes = buildList {
            for (i in 0 until nodesArr.length()) {
                val o = nodesArr.getJSONObject(i)
                add(o.getDouble("lat") to o.getDouble("lon"))
            }
        }
        val matrixObj = root.getJSONObject("route_matrix")
        val matrix = buildMap {
            val it = matrixObj.keys()
            while (it.hasNext()) {
                val k = it.next()
                val cell = matrixObj.getJSONObject(k)
                put(
                    k,
                    ParityMapsAdapter.Leg(
                        cell.getDouble("distance_km"),
                        cell.getDouble("travel_min"),
                    ),
                )
            }
        }
        val adapter = ParityMapsAdapter(nodes, matrix)

        val start = nodes[0]
        val a = nodes[1]
        val b = nodes[2]

        assertEquals(2.0 to 5.0, adapter.getRouteSync(start.first, start.second, a.first, a.second))
        assertEquals(1.5 to 4.0, adapter.getRouteSync(a.first, a.second, b.first, b.second))
        assertEquals(3.0 to 8.0, adapter.getRouteSync(start.first, start.second, b.first, b.second))
    }
}
