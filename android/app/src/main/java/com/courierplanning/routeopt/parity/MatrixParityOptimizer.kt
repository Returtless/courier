package com.courierplanning.routeopt.parity

import com.courierplanning.routeopt.math.DeliveryTimeWindowParser
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToLong

/**
 * Parity path: matrix-only routing, exhaustive permutation search, fitness + route build aligned with
 * [src.services.route_optimizer_genetic.GeneticRouteOptimizer] (_calculate_fitness + core loop of _build_route_from_chromosome).
 *
 * For small N (≤8) picks the chromosome with minimum fitness; sufficient for [parity_fixtures/tiny_two_orders].
 */
object MatrixParityOptimizer {

    private val WINDOW_HH_MM: DateTimeFormatter =
        DateTimeFormatter.ofPattern("HH:mm").withLocale(Locale.ROOT)

    /** Match Python `datetime.isoformat()` for offset datetimes: `2026-01-29T10:00:00+03:00` */
    private val PYTHON_LIKE_DATETIME_ISO: DateTimeFormatter =
        DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ssXXX").withLocale(Locale.ROOT)

    private const val MAX_DELAY_MINUTES = 10.0
    private const val MANUAL_TIME_TOLERANCE = 7.0

    private const val FEASIBLE_TIER = 0.0
    private const val INFEASIBLE_TIER = 1_000_000_000.0
    private const val K_VIOL = 1_000_000.0
    private const val K_DELAY = 5_000.0
    private const val K_CRIT_COUNT = 200_000.0
    private const val K_CRIT_MIN = 10_000.0
    private const val K_MANUAL = 2_000.0
    private const val K_DIST = 10.0
    private const val K_TIME = 5.0

    data class InternalOrder(
        val orderNumber: String,
        val lat: Double,
        val lon: Double,
        val windowStart: LocalTime?,
        val windowEnd: LocalTime?,
        val manualArrival: ZonedDateTime?,
    )

    /**
     * Optimize without clustering (raw JSON order and windows). Prefer [ParityRouteFacade.optimize] for Python parity.
     */
    fun optimize(input: ParityOptimizeInputJson): ParityOptimizeOutputJson {
        val zone = ZonedDateTime.parse(input.startTimeIso).zone
        return optimizeFromOrders(input, buildUnclusteredInternalOrders(input, zone))
    }

    fun optimizeFromOrders(
        input: ParityOptimizeInputJson,
        orders: List<InternalOrder>,
    ): ParityOptimizeOutputJson {
        val startZdt = ZonedDateTime.parse(input.startTimeIso)
        val zone = startZdt.zone
        val orderDate: LocalDate = startZdt.toLocalDate()
        val serviceMin = input.settings.serviceTimeMinutes.toDouble()

        val maps = ParityMapsAdapter(
            input.nodes.map { it.lat to it.lon },
            input.routeMatrix.mapValues { (_, c) ->
                ParityMapsAdapter.Leg(c.distanceKm, c.travelMin)
            },
        )

        if (orders.isEmpty()) {
            return ParityOptimizeOutputJson(
                routePoints = emptyList(),
                totalDistanceKm = 0.0,
                totalTimeMin = 0.0,
                estimatedCompletionIso = startZdt.toPythonIso(),
            )
        }

        val perms = allPermutations(orders.size)
        var best: IntArray? = null
        var bestFit = Double.POSITIVE_INFINITY
        for (p in perms) {
            val f = fitness(
                p, orders, maps,
                input.startLocation.lat, input.startLocation.lon,
                startZdt, orderDate, zone, serviceMin,
            )
            if (f < bestFit) {
                bestFit = f
                best = p
            }
        }

        val route = buildRouteFromChromosome(
            best!!, orders, maps,
            input.startLocation.lat, input.startLocation.lon,
            startZdt, orderDate, zone, serviceMin,
        )

        return toOutputJson(route, orderDate, zone)
    }

    private fun buildUnclusteredInternalOrders(
        input: ParityOptimizeInputJson,
        zone: ZoneId,
    ): List<InternalOrder> =
        input.orders.map { o ->
            InternalOrder(
                orderNumber = o.orderNumber,
                lat = o.lat,
                lon = o.lon,
                windowStart = o.windowStart?.let { DeliveryTimeWindowParser.parseExplicitHhMm(it) },
                windowEnd = o.windowEnd?.let { DeliveryTimeWindowParser.parseExplicitHhMm(it) },
                manualArrival = o.manualArrivalIso?.let { iso ->
                    ZonedDateTime.parse(iso).withZoneSameInstant(zone)
                },
            )
        }

    private fun fitness(
        chromosome: IntArray,
        orders: List<InternalOrder>,
        maps: ParityMapsAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
        orderDate: LocalDate,
        zone: java.time.ZoneId,
        serviceMin: Double,
    ): Double {
        if (chromosome.isEmpty()) return Double.POSITIVE_INFINITY

        var totalDistance = 0.0
        var totalTime = 0.0
        var violations = 0
        var totalDelay = 0.0
        var criticalDelays = 0
        var criticalDelayMinutes = 0.0
        var manualViolations = 0

        var curLat = startLat
        var curLon = startLon
        var curTime = startZdt

        for (idx in chromosome) {
            if (idx !in orders.indices) return Double.POSITIVE_INFINITY
            val order = orders[idx]
            val (dist, travelMin) = try {
                maps.getRouteSync(curLat, curLon, order.lat, order.lon)
            } catch (_: Exception) {
                return Double.POSITIVE_INFINITY
            }

            var arrival = curTime.plusMinutesFp(travelMin)
            val ws = order.windowStart
            val we = order.windowEnd

            if (ws != null && we != null) {
                val windowStart = ZonedDateTime.of(orderDate, ws, zone)
                val windowEnd = ZonedDateTime.of(orderDate, we, zone)
                if (arrival < windowStart) {
                    val waitMin = ChronoUnit.NANOS.between(arrival, windowStart) / 60_000_000_000.0
                    arrival = windowStart
                    totalTime += waitMin
                }
                if (arrival > windowEnd) {
                    violations += 1
                    val delay = ChronoUnit.NANOS.between(windowEnd, arrival) / 60_000_000_000.0
                    if (delay > MAX_DELAY_MINUTES) {
                        criticalDelays += 1
                        criticalDelayMinutes += delay
                        totalDelay += delay
                    } else {
                        totalDelay += delay
                    }
                }
            }

            order.manualArrival?.let { manual ->
                val diffMin = abs(ChronoUnit.NANOS.between(manual, arrival)) / 60_000_000_000.0
                if (diffMin > MANUAL_TIME_TOLERANCE) {
                    manualViolations += 1
                }
            }

            totalDistance += dist
            totalTime += travelMin + serviceMin

            curLat = order.lat
            curLon = order.lon
            curTime = arrival.plusMinutesFp(serviceMin)
        }

        val tier = if (violations > 0 || totalDelay > 0) INFEASIBLE_TIER else FEASIBLE_TIER
        return tier +
            violations * K_VIOL +
            totalDelay * K_DELAY +
            criticalDelays * K_CRIT_COUNT +
            criticalDelayMinutes * K_CRIT_MIN +
            manualViolations * K_MANUAL +
            totalDistance * K_DIST +
            totalTime * K_TIME
    }

    private data class BuiltPoint(
        val order: InternalOrder,
        val arrival: ZonedDateTime,
        val distanceFromPrev: Double,
        val timeFromPrev: Double,
    )

    private data class BuiltRoute(
        val points: List<BuiltPoint>,
        val totalDistance: Double,
        val totalTime: Double,
        val completion: ZonedDateTime,
    )

    private fun buildRouteFromChromosome(
        chromosome: IntArray,
        orders: List<InternalOrder>,
        maps: ParityMapsAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
        orderDate: LocalDate,
        zone: java.time.ZoneId,
        serviceMin: Double,
    ): BuiltRoute {
        val points = mutableListOf<BuiltPoint>()
        var totalDistance = 0.0
        var totalTime = 0.0
        var curLat = startLat
        var curLon = startLon
        var curTime = startZdt

        for (idx in chromosome) {
            if (idx !in orders.indices) continue
            val order = orders[idx]
            val (dist, travelMin) = maps.getRouteSync(curLat, curLon, order.lat, order.lon)
            var arrival = curTime.plusMinutesFp(travelMin)

            order.manualArrival?.let { manual ->
                val diffMin = ChronoUnit.NANOS.between(manual, arrival) / 60_000_000_000.0
                if (abs(diffMin) > MANUAL_TIME_TOLERANCE) {
                    if (diffMin > 0) {
                        if (diffMin <= MANUAL_TIME_TOLERANCE * 2) {
                            arrival = manual.plusMinutesFp(MANUAL_TIME_TOLERANCE)
                        }
                    } else {
                        arrival = manual.plusMinutesFp(-MANUAL_TIME_TOLERANCE)
                        if (arrival < curTime) {
                            arrival = curTime
                        }
                    }
                }
            }

            val ws = order.windowStart
            val we = order.windowEnd
            if (ws != null && we != null) {
                val windowStart = ZonedDateTime.of(orderDate, ws, zone)
                val windowEnd = ZonedDateTime.of(orderDate, we, zone)
                if (arrival < windowStart) {
                    arrival = windowStart
                }
                // late: log only in Python; no clamp
            }

            points.add(BuiltPoint(order, arrival, dist, travelMin))
            totalDistance += dist
            totalTime += travelMin + serviceMin
            curLat = order.lat
            curLon = order.lon
            curTime = arrival.plusMinutesFp(serviceMin)
        }

        return BuiltRoute(points, totalDistance, totalTime, curTime)
    }

    private fun toOutputJson(route: BuiltRoute, orderDate: LocalDate, zone: java.time.ZoneId): ParityOptimizeOutputJson {
        val outs = route.points.map { p ->
            val we = p.order.windowEnd
            val windowEndZdt = if (we != null) ZonedDateTime.of(orderDate, we, zone) else null
            val isLate = windowEndZdt != null && p.arrival > windowEndZdt
            RoutePointOutJson(
                orderNumber = p.order.orderNumber,
                estimatedArrivalIso = p.arrival.toPythonIso(),
                distanceFromPreviousKm = p.distanceFromPrev,
                timeFromPreviousMin = p.timeFromPrev,
                isLate = isLate,
                windowStart = p.order.windowStart?.format(WINDOW_HH_MM),
                windowEnd = p.order.windowEnd?.format(WINDOW_HH_MM),
            )
        }
        return ParityOptimizeOutputJson(
            routePoints = outs,
            totalDistanceKm = route.totalDistance,
            totalTimeMin = route.totalTime,
            estimatedCompletionIso = route.completion.toPythonIso(),
        )
    }

    private fun ZonedDateTime.toPythonIso(): String =
        truncatedTo(ChronoUnit.SECONDS).format(PYTHON_LIKE_DATETIME_ISO)

    private fun ZonedDateTime.plusMinutesFp(minutes: Double): ZonedDateTime {
        val nanos = (minutes * 60_000_000_000.0).roundToLong()
        return this.plusNanos(nanos)
    }

    private fun allPermutations(n: Int): List<IntArray> {
        if (n <= 0) return listOf(intArrayOf())
        val a = IntArray(n) { it }
        val out = mutableListOf<IntArray>()
        fun permute(k: Int) {
            if (k == n) {
                out.add(a.copyOf())
                return
            }
            for (i in k until n) {
                val t = a[k]
                a[k] = a[i]
                a[i] = t
                permute(k + 1)
                val u = a[k]
                a[k] = a[i]
                a[i] = u
            }
        }
        permute(0)
        return out
    }
}
