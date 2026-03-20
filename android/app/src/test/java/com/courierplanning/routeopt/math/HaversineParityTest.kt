package com.courierplanning.routeopt.math

import com.courierplanning.routeopt.testsupport.loadAppTestResourceText
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

class HaversineParityTest {

    @Test
    fun distanceKm_matchesPythonReferenceVectors() {
        val root = JSONObject(loadAppTestResourceText("parity_fixtures/math_vectors/haversine.json"))
        val cases = root.getJSONArray("cases")
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val id = c.getString("id")
            val expected = c.getDouble("distance_km")
            val actual = Haversine.distanceKm(
                c.getDouble("lat1"),
                c.getDouble("lon1"),
                c.getDouble("lat2"),
                c.getDouble("lon2"),
            )
            assertEquals("case $id", expected, actual, 1.0e-9)
        }
    }
}
