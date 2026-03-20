package com.courierplanning.routeopt.math

import java.time.DateTimeException
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException

/**
 * Mirrors [src.models.route_types.Order] behaviour:
 * - [parseWindowString] uses the same regex as `_parse_time_window`
 * - [resolve] applies window string first (if present and yields valid times), else explicit "HH:mm" pair
 * - [minutesFromMidnightRange] matches `get_time_window_minutes`: (0, 24*60) if start or end missing
 */
data class ParsedTimeWindow(
    val start: LocalTime?,
    val end: LocalTime?,
) {
    fun minutesFromMidnightRange(): Pair<Int, Int> {
        if (start == null || end == null) return 0 to (24 * 60)
        val a = start.hour * 60 + start.minute
        val b = end.hour * 60 + end.minute
        return a to b
    }
}

object DeliveryTimeWindowParser {
    private val pattern = Regex("""(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})""")
    private val explicitFormatter = DateTimeFormatter.ofPattern("H:mm")

    /**
     * First regex match in [raw], same as Python `re.search` on the string.
     */
    fun parseWindowString(raw: String?): ParsedTimeWindow {
        if (raw.isNullOrBlank()) return ParsedTimeWindow(null, null)
        val m = pattern.find(raw) ?: return ParsedTimeWindow(null, null)
        val h1 = m.groupValues[1].toInt()
        val m1 = m.groupValues[2].toInt()
        val h2 = m.groupValues[3].toInt()
        val m2 = m.groupValues[4].toInt()
        return try {
            ParsedTimeWindow(
                LocalTime.of(h1, m1),
                LocalTime.of(h2, m2),
            )
        } catch (_: DateTimeException) {
            ParsedTimeWindow(null, null)
        }
    }

    fun parseExplicitHhMm(value: String?): LocalTime? {
        if (value.isNullOrBlank()) return null
        return try {
            LocalTime.parse(value.trim(), explicitFormatter)
        } catch (_: DateTimeParseException) {
            null
        }
    }

    /**
     * Match Python `Order.__init__`: if `delivery_time_window` is set, try parse; explicit start/end used when
     * no window string (test vectors use either window XOR explicit).
     */
    fun resolve(
        deliveryTimeWindow: String?,
        explicitStart: String? = null,
        explicitEnd: String? = null,
    ): ParsedTimeWindow {
        if (!deliveryTimeWindow.isNullOrBlank()) {
            val fromWindow = parseWindowString(deliveryTimeWindow)
            if (fromWindow.start != null && fromWindow.end != null) {
                return fromWindow
            }
        }
        val es = parseExplicitHhMm(explicitStart)
        val ee = parseExplicitHhMm(explicitEnd)
        if (es != null && ee != null) {
            return ParsedTimeWindow(es, ee)
        }
        return ParsedTimeWindow(null, null)
    }
}
