package com.courierplanning.routeopt.math

import com.courierplanning.routeopt.testsupport.loadAppTestResourceText
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class TimeWindowParityTest {

    @Test
    fun resolve_matchesPythonReferenceVectors() {
        val root = JSONObject(loadAppTestResourceText("parity_fixtures/math_vectors/time_windows.json"))
        val cases = root.getJSONArray("cases")
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val id = c.getString("id")
            val window = jsonNullableString(c, "delivery_time_window")
            val exStart = jsonNullableString(c, "explicit_start")
            val exEnd = jsonNullableString(c, "explicit_end")

            val parsed = DeliveryTimeWindowParser.resolve(window, exStart, exEnd)
            val (minStart, minEnd) = parsed.minutesFromMidnightRange()

            assertEquals("case $id minStart", c.getInt("expect_min_from_midnight_start"), minStart)
            assertEquals("case $id minEnd", c.getInt("expect_min_from_midnight_end"), minEnd)

            val esh = jsonNullableInt(c, "expect_start_h")
            val esm = jsonNullableInt(c, "expect_start_m")
            val eeh = jsonNullableInt(c, "expect_end_h")
            val eem = jsonNullableInt(c, "expect_end_m")

            if (esh == null) {
                assertNull("case $id start", parsed.start)
            } else {
                assertEquals("case $id start hour", esh, parsed.start!!.hour)
                assertEquals("case $id start minute", esm!!, parsed.start.minute)
            }
            if (eeh == null) {
                assertNull("case $id end", parsed.end)
            } else {
                assertEquals("case $id end hour", eeh, parsed.end!!.hour)
                assertEquals("case $id end minute", eem!!, parsed.end.minute)
            }
        }
    }

    private fun jsonNullableString(o: JSONObject, key: String): String? {
        if (!o.has(key) || o.isNull(key)) return null
        return o.getString(key)
    }

    private fun jsonNullableInt(o: JSONObject, key: String): Int? {
        if (!o.has(key) || o.isNull(key)) return null
        return o.getInt(key)
    }
}
