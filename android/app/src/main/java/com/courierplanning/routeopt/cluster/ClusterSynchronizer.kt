package com.courierplanning.routeopt.cluster

import com.courierplanning.routeopt.math.Haversine
import java.time.Duration
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime

/**
 * Kotlin port of [src.services.route_optimizer_genetic.GeneticRouteOptimizer._cluster_and_synchronize_orders]
 * and [_synchronize_time_windows]. Sort keys use [zone] from the fixture `start_time_iso` (same idea as
 * combining date+time in Python; for parity run Python export and JVM tests in the same TZ / offset).
 */
object ClusterSynchronizer {
    const val CLUSTER_RADIUS_KM: Double = 0.8

    data class ClusterOrder(
        val orderNumber: String,
        val lat: Double,
        val lon: Double,
        val windowStart: LocalTime?,
        val windowEnd: LocalTime?,
    )

    fun clusterAndSynchronize(
        orders: List<ClusterOrder>,
        orderDate: LocalDate,
        zone: ZoneId,
        startLat: Double,
        startLon: Double,
    ): List<ClusterOrder> {
        if (orders.size <= 1) return orders

        // Match Python: orders_with_coords = [o for o in orders if o.latitude and o.longitude]
        val withCoords = orders.filter { it.lat != 0.0 && it.lon != 0.0 }
        if (withCoords.isEmpty()) return orders

        val clusters = mutableListOf<MutableList<ClusterOrder>>()
        val remaining = withCoords.toMutableList()

        while (remaining.isNotEmpty()) {
            val seed = remaining.removeAt(0)
            val cluster = mutableListOf(seed)
            var clusterWindowStart: ZonedDateTime? = null
            var clusterWindowEnd: ZonedDateTime? = null
            if (seed.windowStart != null && seed.windowEnd != null) {
                clusterWindowStart = ZonedDateTime.of(orderDate, seed.windowStart, zone)
                clusterWindowEnd = ZonedDateTime.of(orderDate, seed.windowEnd, zone)
            }

            var i = 0
            while (i < remaining.size) {
                val order = remaining[i]
                val distance = Haversine.distanceKm(seed.lat, seed.lon, order.lat, order.lon)
                if (distance > CLUSTER_RADIUS_KM) {
                    i++
                    continue
                }
                if (order.windowStart != null && order.windowEnd != null) {
                    val orderStart = ZonedDateTime.of(orderDate, order.windowStart, zone)
                    val orderEnd = ZonedDateTime.of(orderDate, order.windowEnd, zone)
                    if (clusterWindowStart != null && clusterWindowEnd != null) {
                        // intersection non-empty: start1 < end2 && start2 < end1
                        if (!(clusterWindowStart < orderEnd && orderStart < clusterWindowEnd)) {
                            i++
                            continue
                        }
                    } else {
                        clusterWindowStart = orderStart
                        clusterWindowEnd = orderEnd
                    }
                }
                cluster.add(order)
                remaining.removeAt(i)
                if (order.windowStart != null && order.windowEnd != null &&
                    clusterWindowStart != null && clusterWindowEnd != null
                ) {
                    val orderStart = ZonedDateTime.of(orderDate, order.windowStart, zone)
                    val orderEnd = ZonedDateTime.of(orderDate, order.windowEnd, zone)
                    // Union of intervals: min(starts), max(ends) — same as Python cluster_window update
                    clusterWindowStart = minZdt(clusterWindowStart, orderStart)
                    clusterWindowEnd = maxZdt(clusterWindowEnd, orderEnd)
                }
            }
            clusters.add(cluster)
        }

        val sortedClusters = clusters.sortedWith(clusterComparator(orderDate, zone, startLat, startLon))

        val synchronized = mutableListOf<ClusterOrder>()
        for (cl in sortedClusters) {
            if (cl.size > 1) {
                synchronized.addAll(synchronizeTimeWindows(cl, orderDate, zone))
            } else {
                synchronized.addAll(cl)
            }
        }

        return synchronized.sortedWith(orderWindowComparator(orderDate, zone, startLat, startLon))
    }

    private fun minZdt(a: ZonedDateTime, b: ZonedDateTime): ZonedDateTime =
        if (a <= b) a else b

    private fun maxZdt(a: ZonedDateTime, b: ZonedDateTime): ZonedDateTime =
        if (a >= b) a else b

    private fun clusterComparator(
        orderDate: LocalDate,
        zone: ZoneId,
        startLat: Double,
        startLon: Double,
    ): Comparator<MutableList<ClusterOrder>> =
        compareBy(
            { clusterKeyEndEpoch(it, orderDate, zone) },
            { clusterKeyNegMinDuration(it, orderDate) },
            { clusterKeyNegMaxDist(it, startLat, startLon) },
        )

    private fun clusterKeyEndEpoch(cl: List<ClusterOrder>, orderDate: LocalDate, zone: ZoneId): Long {
        var endEpoch = Long.MAX_VALUE
        for (o in cl) {
            val we = o.windowEnd ?: continue
            val zdt = ZonedDateTime.of(orderDate, we, zone)
            endEpoch = minOf(endEpoch, zdt.toEpochSecond())
        }
        return endEpoch
    }

    private fun clusterKeyNegMinDuration(cl: List<ClusterOrder>, orderDate: LocalDate): Double {
        var minDuration = Double.POSITIVE_INFINITY
        for (o in cl) {
            if (o.windowStart == null || o.windowEnd == null) continue
            val minutes = Duration.between(
                LocalDateTime.of(orderDate, o.windowStart),
                LocalDateTime.of(orderDate, o.windowEnd),
            ).toMinutes().toDouble()
            minDuration = minOf(minDuration, minutes)
        }
        return if (minDuration.isFinite()) -minDuration else 0.0
    }

    private fun clusterKeyNegMaxDist(cl: List<ClusterOrder>, startLat: Double, startLon: Double): Double {
        var maxDist = 0.0
        for (o in cl) {
            val d = Haversine.distanceKm(startLat, startLon, o.lat, o.lon)
            maxDist = maxOf(maxDist, d)
        }
        return -maxDist
    }

    private fun orderWindowComparator(
        orderDate: LocalDate,
        zone: ZoneId,
        startLat: Double,
        startLon: Double,
    ): Comparator<ClusterOrder> =
        compareBy(
            { orderKeyEndEpoch(it, orderDate, zone) },
            { orderKeyNegDuration(it, orderDate) },
            { orderKeyNegDist(it, startLat, startLon) },
            { it.orderNumber },
        )

    private fun orderKeyEndEpoch(o: ClusterOrder, orderDate: LocalDate, zone: ZoneId): Long {
        val we = o.windowEnd ?: return Long.MAX_VALUE
        return ZonedDateTime.of(orderDate, we, zone).toEpochSecond()
    }

    private fun orderKeyNegDuration(o: ClusterOrder, orderDate: LocalDate): Double {
        if (o.windowStart == null || o.windowEnd == null) return 0.0
        val minutes = Duration.between(
            LocalDateTime.of(orderDate, o.windowStart),
            LocalDateTime.of(orderDate, o.windowEnd),
        ).toMinutes().toDouble()
        return -minutes
    }

    private fun orderKeyNegDist(o: ClusterOrder, startLat: Double, startLon: Double): Double =
        -Haversine.distanceKm(startLat, startLon, o.lat, o.lon)

    private fun synchronizeTimeWindows(
        cluster: List<ClusterOrder>,
        orderDate: LocalDate,
        zone: ZoneId,
    ): List<ClusterOrder> {
        val withWin = cluster.filter { it.windowStart != null && it.windowEnd != null }
        if (withWin.isEmpty()) return cluster
        if (withWin.size == 1) return cluster

        var commonStart: ZonedDateTime? = null
        var commonEnd: ZonedDateTime? = null
        for (o in withWin) {
            val ws = ZonedDateTime.of(orderDate, o.windowStart!!, zone)
            val we = ZonedDateTime.of(orderDate, o.windowEnd!!, zone)
            if (commonStart == null) {
                commonStart = ws
                commonEnd = we
            } else {
                commonStart = maxZdt(commonStart, ws)
                commonEnd = minZdt(commonEnd!!, we)
            }
        }

        val cs = commonStart!!
        val ce = commonEnd!!
        val durationMin = Duration.between(cs, ce).toMinutes().toDouble()

        return if (cs < ce) {
            if (durationMin >= 30.0) {
                val ns = cs.toLocalTime()
                val ne = ce.toLocalTime()
                cluster.map { o ->
                    if (o.windowStart != null && o.windowEnd != null) {
                        o.copy(windowStart = ns, windowEnd = ne)
                    } else {
                        o
                    }
                }
            } else {
                val narrow = withWin.minByOrNull { o ->
                    Duration.between(
                        LocalDateTime.of(orderDate, o.windowStart!!),
                        LocalDateTime.of(orderDate, o.windowEnd!!),
                    ).toSeconds().toDouble()
                }!!
                val ts = narrow.windowStart!!
                val te = narrow.windowEnd!!
                cluster.map { o ->
                    if (o.windowStart != null && o.windowEnd != null) {
                        o.copy(windowStart = ts, windowEnd = te)
                    } else {
                        o
                    }
                }
            }
        } else {
            val narrow = withWin.minByOrNull { o ->
                Duration.between(
                    LocalDateTime.of(orderDate, o.windowStart!!),
                    LocalDateTime.of(orderDate, o.windowEnd!!),
                ).toSeconds().toDouble()
            }!!
            val ts = narrow.windowStart!!
            val te = narrow.windowEnd!!
            cluster.map { o ->
                if (o.windowStart != null && o.windowEnd != null) {
                    o.copy(windowStart = ts, windowEnd = te)
                } else {
                    o
                }
            }
        }
    }
}
