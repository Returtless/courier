package com.courierplanning.routeopt.genetic

import com.courierplanning.routeopt.core.MatrixRoutingAdapter
import com.courierplanning.routeopt.parity.MatrixParityOptimizer
import com.courierplanning.routeopt.parity.MatrixParityOptimizer.BuiltPoint
import com.courierplanning.routeopt.parity.MatrixParityOptimizer.BuiltRoute
import com.courierplanning.routeopt.parity.MatrixParityOptimizer.InternalOrder
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.temporal.ChronoUnit
import kotlin.math.roundToLong

/**
 * Постобработка маршрута как в Python [src.services.route_optimizer_genetic.GeneticRouteOptimizer._build_route_from_chromosome]:
 * при опозданиях — [_fix_delays_in_route], затем [_rescue_feasibility] + снова fix, затем [_polish_route_by_distance].
 */
object GeneticRoutePostProcessor {

    private const val WINDOW_END_TOLERANCE_MIN = 1.0
    private const val MAX_DELAY_MIN = 10.0
    private const val MAX_FIX_MOVES = 8

    fun applyBotPostProcess(
        initialRoute: BuiltRoute,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
        serviceMin: Double,
    ): BuiltRoute {
        if (initialRoute.points.isEmpty()) return initialRoute
        val orderDate = startZdt.toLocalDate()
        val zone = startZdt.zone

        val totalDelaysStrict = totalDelayMinutesStrict(initialRoute, orderDate, zone)
        var routeAfterFix = initialRoute
        if (totalDelaysStrict > 0) {
            fixDelaysInRoute(
                initialRoute,
                maps,
                startLat,
                startLon,
                startZdt,
                serviceMin,
                orderDate,
                zone,
            )?.let { if (it.points.isNotEmpty()) routeAfterFix = it }
        }

        var result = routeAfterFix
        val rescued = rescueFeasibility(
            routeAfterFix,
            maps,
            startLat,
            startLon,
            startZdt,
            serviceMin,
            orderDate,
            zone,
        )
        if (rescued.points.isNotEmpty()) {
            val finalFixed = fixDelaysInRoute(
                rescued,
                maps,
                startLat,
                startLon,
                startZdt,
                serviceMin,
                orderDate,
                zone,
            )
            result = when {
                finalFixed != null && finalFixed.points.isNotEmpty() -> finalFixed
                else -> rescued
            }
        }

        val polished = polishRouteByDistance(
            result,
            maps,
            startLat,
            startLon,
            startZdt,
            serviceMin,
            orderDate,
            zone,
        )
        return if (polished.points.isNotEmpty()) polished else result
    }

    private fun totalDelayMinutesStrict(route: BuiltRoute, orderDate: LocalDate, zone: ZoneId): Double {
        var total = 0.0
        for (p in route.points) {
            val o = p.order
            val we = o.windowEnd ?: continue
            o.windowStart ?: continue
            val windowEnd = ZonedDateTime.of(orderDate, we, zone)
            if (p.arrival > windowEnd) {
                total += ChronoUnit.NANOS.between(windowEnd, p.arrival) / 60_000_000_000.0
            }
        }
        return total
    }

    private fun routeDelayStats(
        route: BuiltRoute,
        orderDate: LocalDate,
        zone: ZoneId,
    ): Triple<Double, Int, Boolean> {
        var total = 0.0
        var count = 0
        var hasCritical = false
        for (p in route.points) {
            val o = p.order
            val ws = o.windowStart ?: continue
            val we = o.windowEnd ?: continue
            val windowEnd = ZonedDateTime.of(orderDate, we, zone)
            val tolEnd = windowEnd.plusMinutes(WINDOW_END_TOLERANCE_MIN.toLong())
            if (!p.arrival.isAfter(tolEnd)) continue
            val d = ChronoUnit.NANOS.between(windowEnd, p.arrival) / 60_000_000_000.0
            total += d
            count++
            if (d > MAX_DELAY_MIN) hasCritical = true
        }
        return Triple(total, count, hasCritical)
    }

    private fun collectDelayedIndices(
        route: BuiltRoute,
        orderDate: LocalDate,
        zone: ZoneId,
    ): List<Triple<Int, BuiltPoint, Double>> {
        val out = mutableListOf<Triple<Int, BuiltPoint, Double>>()
        for ((idx, p) in route.points.withIndex()) {
            val o = p.order
            val ws = o.windowStart ?: continue
            val we = o.windowEnd ?: continue
            val windowEnd = ZonedDateTime.of(orderDate, we, zone)
            val tolEnd = windowEnd.plusMinutes(WINDOW_END_TOLERANCE_MIN.toLong())
            if (!p.arrival.isAfter(tolEnd)) continue
            val d = ChronoUnit.NANOS.between(windowEnd, p.arrival) / 60_000_000_000.0
            if (d > WINDOW_END_TOLERANCE_MIN) {
                out.add(Triple(idx, p, d))
            }
        }
        out.sortByDescending { it.third }
        return out
    }

    private fun recalculate(
        sequence: List<InternalOrder>,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
        serviceMin: Double,
        orderDate: LocalDate,
        zone: ZoneId,
    ): BuiltRoute? =
        MatrixParityOptimizer.recalculateRouteFromOrderSequence(
            sequence,
            maps,
            startLat,
            startLon,
            startZdt,
            orderDate,
            zone,
            serviceMin,
        )

    private fun tryEfp(
        pointsList: List<InternalOrder>,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
        serviceMin: Double,
        orderDate: LocalDate,
        zone: ZoneId,
    ): Pair<MutableList<InternalOrder>?, Boolean> {
        val route = recalculate(pointsList, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone)
            ?: return null to false
        val (_, countNow, _) = routeDelayStats(route, orderDate, zone)
        if (countNow == 0) return null to false

        val tolEndExtra = WINDOW_END_TOLERANCE_MIN.toLong()
        val delayed = collectDelayedIndices(route, orderDate, zone)
        for ((idx, delayedPoint, _) in delayed) {
            for (k in 0 until idx) {
                val base = pointsList.toMutableList()
                val removed = base.removeAt(idx)
                base.add(k, removed)
                val trial = recalculate(base, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone)
                    ?: continue
                val (tTotal, tCount, tCritical) = routeDelayStats(trial, orderDate, zone)
                if (tCritical || tCount > countNow) continue

                val movedNum = delayedPoint.order.orderNumber
                var movedOnTime = true
                for (p in trial.points) {
                    if (p.order.orderNumber != movedNum) continue
                    val o = p.order
                    val we = o.windowEnd ?: break
                    val ws = o.windowStart ?: break
                    val weZdt = ZonedDateTime.of(orderDate, we, zone)
                    val deadline = weZdt.plusMinutes(tolEndExtra)
                    if (p.arrival.isAfter(deadline)) movedOnTime = false
                    break
                }
                if (movedOnTime) return base to true
            }
        }
        return null to false
    }

    private fun trySwapWithLaterWindow(
        pointsList: List<InternalOrder>,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
        serviceMin: Double,
        orderDate: LocalDate,
        zone: ZoneId,
        totalNow: Double,
        countNow: Int,
    ): Pair<MutableList<InternalOrder>?, Boolean> {
        val route = recalculate(pointsList, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone)
            ?: return null to false
        val delayed = collectDelayedIndices(route, orderDate, zone)
        if (delayed.isEmpty()) return null to false
        for ((idx, delayedPoint, _) in delayed) {
            val oLate = delayedPoint.order
            val weLate = oLate.windowEnd ?: continue
            val weLateZdt = ZonedDateTime.of(orderDate, weLate, zone)
            for (k in 0 until idx) {
                val oEarly = pointsList[k]
                val weEarly = oEarly.windowEnd ?: continue
                val weEarlyZdt = ZonedDateTime.of(orderDate, weEarly, zone)
                if (weEarlyZdt <= weLateZdt) continue
                val swapPoints = pointsList.toMutableList()
                val t = swapPoints[idx]
                swapPoints[idx] = swapPoints[k]
                swapPoints[k] = t
                val trial = recalculate(swapPoints, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone)
                    ?: continue
                val (tTotal, tCount, tCritical) = routeDelayStats(trial, orderDate, zone)
                if (tCritical || tCount > countNow) continue
                if (tTotal < totalNow || (tTotal == totalNow && tCount < countNow)) {
                    return swapPoints to true
                }
            }
        }
        return null to false
    }

    private fun tailIndices(n: Int, k: Int): List<Int> {
        val kk = minOf(k, n)
        return (n - kk until n).toList()
    }

    private fun <T> permutationsOf(list: List<T>): List<List<T>> {
        if (list.isEmpty()) return listOf(emptyList())
        if (list.size == 1) return listOf(list)
        val out = mutableListOf<List<T>>()
        for (i in list.indices) {
            val head = list[i]
            val rest = list.filterIndexed { j, _ -> j != i }
            for (sub in permutationsOf(rest)) {
                out.add(listOf(head) + sub)
            }
        }
        return out
    }

    private fun tryTailPermutation(
        pointsList: List<InternalOrder>,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
        serviceMin: Double,
        orderDate: LocalDate,
        zone: ZoneId,
        totalNow: Double,
        countNow: Int,
    ): Pair<MutableList<InternalOrder>?, Boolean> {
        val n = pointsList.size
        val k = minOf(6, n)
        val tailIdx = tailIndices(n, k)
        val prefix = pointsList.take(n - k)
        var bestPoints: MutableList<InternalOrder>? = null
        var bestTotal = totalNow
        var bestCount = countNow
        val tailOrders = tailIdx.map { pointsList[it] }
        for (perm in permutationsOf(tailOrders)) {
            val candidate = (prefix + perm).toMutableList()
            val trial = recalculate(candidate, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone)
                ?: continue
            val (tTotal, tCount, tCritical) = routeDelayStats(trial, orderDate, zone)
            if (tCritical || tCount > countNow) continue
            if (tTotal < bestTotal || (tTotal == bestTotal && tCount < bestCount)) {
                bestTotal = tTotal
                bestCount = tCount
                bestPoints = candidate
            }
        }
        if (bestPoints == null) return null to false
        if (!(bestTotal < totalNow || (bestTotal == totalNow && bestCount < countNow))) return null to false
        return bestPoints to true
    }

    private fun blocksFor(n: Int, idx: Int, delayedIdx: Set<Int>): List<List<Int>> {
        val out = mutableListOf<List<Int>>()
        val candidates = listOf(
            idx - 1 to idx,
            idx to idx + 1,
            idx - 2 to idx,
            idx - 1 to idx + 1,
            idx to idx + 2,
        )
        for ((start, end) in candidates) {
            if (start < 0 || end >= n || end <= start) continue
            val block = (start..end).toList()
            if (block.any { it in delayedIdx }) out.add(block)
        }
        return out
    }

    private fun tryBlockMove(
        pointsList: List<InternalOrder>,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
        serviceMin: Double,
        orderDate: LocalDate,
        zone: ZoneId,
        totalNow: Double,
        countNow: Int,
        delayedPoints: List<Triple<Int, BuiltPoint, Double>>,
    ): Pair<MutableList<InternalOrder>?, Boolean> {
        val n = pointsList.size
        val delayedIdx = delayedPoints.map { it.first }.toSet()
        var bestPoints: MutableList<InternalOrder>? = null
        var bestTotal = totalNow
        var bestCount = countNow
        for ((idx, _, _) in delayedPoints) {
            for (block in blocksFor(n, idx, delayedIdx)) {
                val insertMax = block.min()
                for (pos in 0 until insertMax) {
                    val base = pointsList.toMutableList()
                    val removed = block.map { base[it] }
                    for (i in block.sortedDescending()) {
                        base.removeAt(i)
                    }
                    for (i in removed.indices) {
                        base.add(pos + i, removed[i])
                    }
                    val trial = recalculate(base, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone)
                        ?: continue
                    val (tTotal, tCount, tCritical) = routeDelayStats(trial, orderDate, zone)
                    if (tCritical || tCount > countNow) continue
                    if (tTotal < bestTotal || (tTotal == bestTotal && tCount < bestCount)) {
                        bestTotal = tTotal
                        bestCount = tCount
                        bestPoints = base
                    }
                }
            }
        }
        if (bestPoints == null) return null to false
        if (!(bestTotal < totalNow || (bestTotal == totalNow && bestCount < countNow))) return null to false
        return bestPoints to true
    }

    private fun fixDelaysInRoute(
        route: BuiltRoute,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
        serviceMin: Double,
        orderDate: LocalDate,
        zone: ZoneId,
    ): BuiltRoute? {
        if (route.points.isEmpty()) return null
        var sequence = route.points.map { it.order }.toMutableList()
        var movesDone = 0
        while (movesDone < MAX_FIX_MOVES) {
            val currentRoute = recalculate(sequence, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone)
                ?: break
            val (totalNow, countNow, _) = routeDelayStats(currentRoute, orderDate, zone)
            if (countNow == 0) return currentRoute

            val delayedRoutePoints = collectDelayedIndices(currentRoute, orderDate, zone)
            var improved = false

            val (efpPoints, efpOk) = tryEfp(
                sequence, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone,
            )
            if (efpOk && efpPoints != null) {
                sequence = efpPoints
                movesDone++
                improved = true
                continue
            }

            val (swapPoints, swapOk) = trySwapWithLaterWindow(
                sequence, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone, totalNow, countNow,
            )
            if (swapOk && swapPoints != null) {
                sequence = swapPoints
                movesDone++
                improved = true
                continue
            }

            val (tailPoints, tailOk) = tryTailPermutation(
                sequence, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone, totalNow, countNow,
            )
            if (tailOk && tailPoints != null) {
                sequence = tailPoints
                movesDone++
                improved = true
                continue
            }

            var bestPoints: MutableList<InternalOrder>? = null
            var bestTotal = totalNow
            var bestCount = countNow
            val nn = sequence.size
            for ((idx, _, _) in delayedRoutePoints) {
                val candidates = (0 until nn).filter { it != idx }
                for (newPos in candidates) {
                    val base = sequence.toMutableList()
                    val removed = base.removeAt(idx)
                    val newPosAdj = if (newPos > idx) newPos - 1 else newPos
                    base.add(newPosAdj, removed)
                    val trialRoute = recalculate(base, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone)
                        ?: continue
                    val (tTotal, tCount, tCritical) = routeDelayStats(trialRoute, orderDate, zone)
                    if (tCritical || tCount > countNow) continue
                    if (tTotal < bestTotal || (tTotal == bestTotal && tCount < bestCount)) {
                        bestTotal = tTotal
                        bestCount = tCount
                        bestPoints = base
                    }
                    if (newPos < idx) {
                        val swapList = sequence.toMutableList()
                        val tmp = swapList[idx]
                        swapList[idx] = swapList[newPos]
                        swapList[newPos] = tmp
                        val swapRoute = recalculate(
                            swapList, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone,
                        ) ?: continue
                        val (sTotal, sCount, sCritical) = routeDelayStats(swapRoute, orderDate, zone)
                        if (sCritical || sCount > countNow) continue
                        if (sTotal < bestTotal || (sTotal == bestTotal && sCount < bestCount)) {
                            bestTotal = sTotal
                            bestCount = sCount
                            bestPoints = swapList
                        }
                    }
                }
            }
            if (bestPoints != null &&
                (bestTotal < totalNow || (bestTotal == totalNow && bestCount < countNow))
            ) {
                sequence = bestPoints
                movesDone++
                improved = true
                continue
            }

            val (blockPoints, blockOk) = tryBlockMove(
                sequence, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone,
                totalNow, countNow, delayedRoutePoints,
            )
            if (blockOk && blockPoints != null) {
                sequence = blockPoints
                movesDone++
                improved = true
                continue
            }

            if (!improved) break
        }
        return recalculate(sequence, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone) ?: route
    }

    private fun evalRescueSequence(
        seq: List<InternalOrder>,
        subStartLat: Double,
        subStartLon: Double,
        subStartZdt: ZonedDateTime,
        orderDate: LocalDate,
        zone: ZoneId,
        maps: MatrixRoutingAdapter,
        serviceMin: Double,
    ): Pair<Double, Double> {
        var curLat = subStartLat
        var curLon = subStartLon
        var curTime = subStartZdt
        var totalDelay = 0.0
        var totalDistance = 0.0
        for (order in seq) {
            val (dist, travelMin) = try {
                maps.getRouteSync(curLat, curLon, order.lat, order.lon)
            } catch (_: Exception) {
                return Double.POSITIVE_INFINITY to Double.POSITIVE_INFINITY
            }
            curLat = order.lat
            curLon = order.lon
            var arrival = curTime.plusNanos((travelMin * 60_000_000_000.0).roundToLong())
            val ws = order.windowStart
            val we = order.windowEnd
            if (ws != null && we != null) {
                val wStart = ZonedDateTime.of(orderDate, ws, zone)
                val wEnd = ZonedDateTime.of(orderDate, we, zone)
                if (arrival < wStart) arrival = wStart
                if (arrival > wEnd) {
                    totalDelay += ChronoUnit.NANOS.between(wEnd, arrival) / 60_000_000_000.0
                }
            }
            totalDistance += dist
            curTime = arrival.plusNanos((serviceMin * 60_000_000_000.0).roundToLong())
        }
        return totalDelay to totalDistance
    }

    private fun optimizeSubrouteByTimeWindows(
        rescueOrders: List<InternalOrder>,
        subStartLat: Double,
        subStartLon: Double,
        subStartZdt: ZonedDateTime,
        orderDate: LocalDate,
        zone: ZoneId,
        maps: MatrixRoutingAdapter,
        serviceMin: Double,
    ): List<InternalOrder>? {
        if (rescueOrders.isEmpty()) return null
        val n = rescueOrders.size
        val maxExact = 8
        if (n <= maxExact) {
            var bestSeq: List<InternalOrder>? = null
            var bestDelay = Double.POSITIVE_INFINITY
            var bestDist = Double.POSITIVE_INFINITY
            for (perm in permutationsOf(rescueOrders)) {
                val (td, dist) = evalRescueSequence(
                    perm, subStartLat, subStartLon, subStartZdt, orderDate, zone, maps, serviceMin,
                )
                if (td < bestDelay || (td == bestDelay && dist < bestDist)) {
                    bestDelay = td
                    bestDist = dist
                    bestSeq = perm
                }
            }
            return bestSeq
        }
        val heuristic = rescueOrders.sortedWith(
            compareBy<InternalOrder>(
                { o ->
                    o.windowEnd?.let { ZonedDateTime.of(orderDate, it, zone).toEpochSecond() } ?: Long.MAX_VALUE
                },
                { o ->
                    if (o.windowStart == null || o.windowEnd == null) {
                        0L
                    } else {
                        val a = ZonedDateTime.of(orderDate, o.windowStart!!, zone)
                        val b = ZonedDateTime.of(orderDate, o.windowEnd!!, zone)
                        -ChronoUnit.MINUTES.between(a, b)
                    }
                },
            ),
        )
        val (td, _) = evalRescueSequence(
            heuristic, subStartLat, subStartLon, subStartZdt, orderDate, zone, maps, serviceMin,
        )
        return if (td < Double.POSITIVE_INFINITY) heuristic else null
    }

    private fun rescueFeasibility(
        route: BuiltRoute,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
        serviceMin: Double,
        orderDate: LocalDate,
        zone: ZoneId,
    ): BuiltRoute {
        if (route.points.isEmpty()) return route
        val (totalNow, countNow, _) = routeDelayStats(route, orderDate, zone)
        if (countNow == 0) return route

        val latePoints = mutableListOf<Triple<Int, BuiltPoint, Double>>()
        for ((idx, p) in route.points.withIndex()) {
            val o = p.order
            val we = o.windowEnd ?: continue
            val ws = o.windowStart ?: continue
            val weZdt = ZonedDateTime.of(orderDate, we, zone)
            if (p.arrival > weZdt) {
                val d = ChronoUnit.NANOS.between(weZdt, p.arrival) / 60_000_000_000.0
                if (d > 0) latePoints.add(Triple(idx, p, d))
            }
        }
        if (latePoints.isEmpty()) return route
        latePoints.sortByDescending { it.third }

        val n = route.points.size
        val rescueIndices = mutableSetOf<Int>()
        for ((idx, _, _) in latePoints) {
            for (offset in -2..2) {
                val j = idx + offset
                if (j in 0 until n) rescueIndices.add(j)
            }
        }
        var latestLateWindowEnd: ZonedDateTime? = null
        for ((_, p, _) in latePoints) {
            val we = p.order.windowEnd ?: continue
            val weZdt = ZonedDateTime.of(orderDate, we, zone)
            if (latestLateWindowEnd == null || weZdt < latestLateWindowEnd) {
                latestLateWindowEnd = weZdt
            }
        }
        if (latestLateWindowEnd != null) {
            for (idx in 0 until n) {
                val we = route.points[idx].order.windowEnd ?: continue
                val weZdt = ZonedDateTime.of(orderDate, we, zone)
                if (!weZdt.isAfter(latestLateWindowEnd)) rescueIndices.add(idx)
            }
        }
        val maxRescueAfterExpand = 12
        val maxRescue = 8
        if (rescueIndices.size > maxRescueAfterExpand) {
            val sorted = rescueIndices.sorted().take(maxRescueAfterExpand).toMutableSet()
            rescueIndices.clear()
            rescueIndices.addAll(sorted)
        }

        if (rescueIndices.isEmpty()) return route

        val rescueIndicesSorted = rescueIndices.sorted()
        val prefixEnd = rescueIndicesSorted.first()
        val prefixPoints = route.points.take(prefixEnd)
        val rescueOrders = rescueIndicesSorted.map { route.points[it].order }
        val tailPoints = route.points.filterIndexed { i, _ ->
            i >= prefixEnd && i !in rescueIndices
        }

        val (subStartLat, subStartLon, subStartZdt) = if (prefixPoints.isNotEmpty()) {
            val last = prefixPoints.last()
            val st = last.arrival.plusNanos((serviceMin * 60_000_000_000.0).roundToLong())
            Triple(last.order.lat, last.order.lon, st)
        } else {
            Triple(startLat, startLon, startZdt)
        }

        val bestSeq = optimizeSubrouteByTimeWindows(
            rescueOrders,
            subStartLat,
            subStartLon,
            subStartZdt,
            orderDate,
            zone,
            maps,
            serviceMin,
        ) ?: return route

        val combined = mutableListOf<InternalOrder>()
        for (p in prefixPoints) combined.add(p.order)
        combined.addAll(bestSeq)
        for (p in tailPoints) combined.add(p.order)

        val newRoute = recalculate(combined, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone)
            ?: return route
        val (newTotal, newCount, newCritical) = routeDelayStats(newRoute, orderDate, zone)
        if (newCritical) return route
        if (newCount == 0 && countNow > 0) return newRoute
        if (newCount <= countNow &&
            (newTotal < totalNow || (newTotal == totalNow && newCount < countNow))
        ) {
            return newRoute
        }
        return route
    }

    private fun polishRouteByDistance(
        route: BuiltRoute,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
        serviceMin: Double,
        orderDate: LocalDate,
        zone: ZoneId,
    ): BuiltRoute {
        if (route.points.size < 2) return route
        var pointsList = route.points.map { it.order }.toMutableList()
        var improved = true
        while (improved) {
            improved = false
            val current = recalculate(pointsList, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone)
                ?: break
            val (totalDelay, countDelay, hasCritical) = routeDelayStats(current, orderDate, zone)
            if (countDelay > 0 || hasCritical) break
            val distNow = current.totalDistance
            for (i in 0 until pointsList.size - 1) {
                val oi = pointsList[i]
                val oj = pointsList[i + 1]
                val wei = oi.windowEnd
                val wej = oj.windowEnd
                if (wei == null || wej == null || wei != wej) continue
                val swapped = pointsList.toMutableList().also {
                    val t = it[i]
                    it[i] = it[i + 1]
                    it[i + 1] = t
                }
                val trial = recalculate(swapped, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone)
                    ?: continue
                if (trial.totalDistance >= distNow) continue
                val (tTotal, tCount, tCritical) = routeDelayStats(trial, orderDate, zone)
                if (tCount > 0 || tCritical) continue
                pointsList = swapped
                improved = true
                break
            }
        }
        return recalculate(pointsList, maps, startLat, startLon, startZdt, serviceMin, orderDate, zone) ?: route
    }
}
