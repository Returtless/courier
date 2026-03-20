package com.courierplanning.routeopt.genetic

import com.courierplanning.routeopt.core.MatrixRoutingAdapter
import com.courierplanning.routeopt.math.Haversine
import com.courierplanning.routeopt.parity.MatrixParityOptimizer
import com.courierplanning.routeopt.parity.ParityOptimizeOutputJson
import com.courierplanning.routeopt.parity.RoutePointOutJson
import com.courierplanning.routeopt.rng.SplitMix64Rng
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToLong

private typealias OptOrder = MatrixParityOptimizer.InternalOrder

/**
 * Kotlin port of [src.services.route_optimizer_genetic.GeneticRouteOptimizer] GA loop + greedy + OX/mutate/repair,
 * using [SplitMix64Rng] when constructed with a seed (parity with Python export).
 *
 * Post-process: recalculate + polish-by-distance (same idea as Python); fix_delays/rescue omitted when
 * no late points (common for parity fixtures). If needed, extend to match Python byte-for-byte.
 */
class KotlinGeneticRouteOptimizer(
    private val rng: SplitMix64Rng,
    private val serviceMin: Double,
) {
    private val windowHhMm: DateTimeFormatter =
        DateTimeFormatter.ofPattern("HH:mm").withLocale(Locale.ROOT)
    private val pythonIso: DateTimeFormatter =
        DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ssXXX").withLocale(Locale.ROOT)

    private companion object {
        const val POPULATION_SIZE = 80
        const val MAX_GENERATIONS = 200
        const val TOURNAMENT_SIZE = 3
        const val CROSSOVER_RATE = 0.8
        const val MUTATION_RATE = 0.2
        const val ELITISM_COUNT = 10
        const val MAX_DELAY_MINUTES = 10.0
        const val MANUAL_TIME_TOLERANCE = 7.0
        const val WINDOW_END_TOLERANCE_MINUTES = 1.0
        const val GREEDY_EST_KM_PER_MIN = 0.5
        private val EARLY_WINDOW_END: LocalTime = LocalTime.of(13, 0)

        const val FEASIBLE_TIER = 0.0
        const val INFEASIBLE_TIER = 1_000_000_000.0
        const val K_VIOL = 1_000_000.0
        const val K_DELAY = 5_000.0
        const val K_CRIT_COUNT = 200_000.0
        const val K_CRIT_MIN = 10_000.0
        const val K_MANUAL = 2_000.0
        const val K_DIST = 10.0
        const val K_TIME = 5.0
    }

    data class GPoint(
        val order: OptOrder,
        val arrival: ZonedDateTime,
        val distanceFromPrev: Double,
        val timeFromPrev: Double,
    )

    data class GRoute(
        val points: List<GPoint>,
        val totalDistance: Double,
        val totalTime: Double,
        val completion: ZonedDateTime,
    )

    fun optimize(
        orders: List<OptOrder>,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
    ): ParityOptimizeOutputJson {
        if (orders.isEmpty()) {
            return ParityOptimizeOutputJson(
                routePoints = emptyList(),
                totalDistanceKm = 0.0,
                totalTimeMin = 0.0,
                estimatedCompletionIso = startZdt.truncatedTo(ChronoUnit.SECONDS).format(pythonIso),
            )
        }
        if (orders.size == 1) {
            val route = buildSingleOrderRoute(orders[0], maps, startLat, startLon, startZdt)
            return toOutputJson(route, startZdt.toLocalDate(), startZdt.zone)
        }

        val zone = startZdt.zone
        val orderDate = startZdt.toLocalDate()
        val n = orders.size

        var population = generateInitialPopulation(orders, startLat, startLon, startZdt)
        var fitnessScores = population.map { fitness(it, orders, maps, startLat, startLon, startZdt) }

        var bestIdx = fitnessScores.indices.minBy { fitnessScores[it] }
        var bestFitness = fitnessScores[bestIdx]
        var bestChromosome = population[bestIdx].copyOf()

        var generation = 0
        var stagnation = 0
        while (generation < MAX_GENERATIONS) {
            val newPop = mutableListOf<IntArray>()
            val eliteIdx = fitnessScores.indices.sortedBy { fitnessScores[it] }.take(ELITISM_COUNT)
            for (i in eliteIdx) newPop.add(population[i].copyOf())

            while (newPop.size < POPULATION_SIZE) {
                val p1 = tournamentSelection(population, fitnessScores)
                val p2 = tournamentSelection(population, fitnessScores)
                val child = if (rng.random() < CROSSOVER_RATE) {
                    orderCrossover(p1, p2)
                } else {
                    if (rng.random() < 0.5) p1.copyOf() else p2.copyOf()
                }
                val mutated = if (rng.random() < MUTATION_RATE) {
                    mutate(child, orders, startZdt)
                } else {
                    child
                }
                repairWindowOrder(mutated, orders, startZdt)
                if (isValidChromosome(mutated, n)) {
                    newPop.add(mutated)
                }
            }
            population = newPop
            fitnessScores = population.map { fitness(it, orders, maps, startLat, startLon, startZdt) }
            val curBest = fitnessScores.indices.minBy { fitnessScores[it] }
            val curFit = fitnessScores[curBest]
            if (curFit < bestFitness) {
                bestFitness = curFit
                bestChromosome = population[curBest].copyOf()
                stagnation = 0
            } else {
                stagnation++
            }
            generation++
            if (stagnation >= 30) break
        }

        repairWindowOrder(bestChromosome, orders, startZdt)
        var route = buildRouteFromChromosome(bestChromosome, orders, maps, startLat, startLon, startZdt)
        route = polishRouteByDistance(route, orders, maps, startLat, startLon, startZdt)
        return toOutputJson(route, orderDate, zone)
    }

    private fun buildSingleOrderRoute(
        order: OptOrder,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
    ): GRoute {
        val (dist, travelMin) = maps.getRouteSync(startLat, startLon, order.lat, order.lon)
        var arrival = startZdt.plusMinutesFp(travelMin)
        val od = startZdt.toLocalDate()
        val zone = startZdt.zone
        order.manualArrival?.let { manual ->
            val diffMin = ChronoUnit.NANOS.between(manual, arrival) / 60_000_000_000.0
            if (abs(diffMin) > MANUAL_TIME_TOLERANCE) {
                if (diffMin > 0 && diffMin <= MANUAL_TIME_TOLERANCE * 2) {
                    arrival = manual.plusMinutesFp(MANUAL_TIME_TOLERANCE)
                } else if (diffMin < 0) {
                    arrival = manual.plusMinutesFp(-MANUAL_TIME_TOLERANCE)
                    if (arrival < startZdt) arrival = startZdt
                }
            }
        }
        val ws = order.windowStart
        val we = order.windowEnd
        if (ws != null && we != null) {
            val wStart = ZonedDateTime.of(od, ws, zone)
            if (arrival < wStart) arrival = wStart
        }
        val completion = arrival.plusMinutesFp(serviceMin)
        val totalTime = travelMin + serviceMin
        return GRoute(
            listOf(GPoint(order, arrival, dist, travelMin)),
            dist,
            totalTime,
            completion,
        )
    }

    private fun generateInitialPopulation(
        orders: List<OptOrder>,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
    ): List<IntArray> {
        val numOrders = orders.size
        val pop = mutableListOf<IntArray>()
        val orderDate = startZdt.toLocalDate()
        val zone = startZdt.zone

        fun shuffledPerm(): IntArray {
            val m = (0 until numOrders).toMutableList()
            rng.shuffle(m)
            return m.toIntArray()
        }
        repeat(POPULATION_SIZE / 4) { pop.add(shuffledPerm()) }

        val indicesByEnd = mutableMapOf<Long, MutableList<Int>>()
        for (i in 0 until numOrders) {
            val o = orders[i]
            val k = if (o.windowEnd != null) {
                ZonedDateTime.of(orderDate, o.windowEnd, zone).toEpochSecond()
            } else {
                Long.MAX_VALUE
            }
            indicesByEnd.getOrPut(k) { mutableListOf() }.add(i)
        }
        repeat(POPULATION_SIZE / 4) {
            val chrom = mutableListOf<Int>()
            for (endTs in indicesByEnd.keys.sorted()) {
                val group = indicesByEnd[endTs]!!.toMutableList()
                rng.shuffle(group)
                chrom.addAll(group)
            }
            pop.add(chrom.toIntArray())
        }

        repeat(POPULATION_SIZE / 8) {
            val sortedIdx = (0 until numOrders).sortedBy { i ->
                val o = orders[i]
                if (o.windowStart != null) {
                    ZonedDateTime.of(orderDate, o.windowStart, zone).toEpochSecond()
                } else {
                    Long.MAX_VALUE
                }
            }
            val chrom = sortedIdx.toMutableList()
            repeat(rng.randInt(0, numOrders / 3)) {
                val p = rng.sampleRange(numOrders, 2)
                val i = p[0]
                val j = p[1]
                val tmp = chrom[i]
                chrom[i] = chrom[j]
                chrom[j] = tmp
            }
            pop.add(chrom.toIntArray())
        }

        fun endAndWidth(i: Int): Pair<Long, Double> {
            val o = orders[i]
            if (o.windowEnd == null) return Long.MAX_VALUE to 0.0
            val endTs = ZonedDateTime.of(orderDate, o.windowEnd, zone).toEpochSecond()
            if (o.windowStart == null) return endTs to 0.0
            val dur = ChronoUnit.MINUTES.between(
                ZonedDateTime.of(orderDate, o.windowStart, zone),
                ZonedDateTime.of(orderDate, o.windowEnd, zone),
            ).toDouble()
            return endTs to -dur
        }
        repeat(POPULATION_SIZE / 8) {
            val sortedIdx = (0 until numOrders).sortedBy { endAndWidth(it) }
            val chrom = sortedIdx.toMutableList()
            repeat(rng.randInt(0, numOrders / 4)) {
                val p = rng.sampleRange(numOrders, 2)
                val i = p[0]
                val j = p[1]
                val tmp = chrom[i]
                chrom[i] = chrom[j]
                chrom[j] = tmp
            }
            pop.add(chrom.toIntArray())
        }

        val strictByWindow = (0 until numOrders).sortedBy { endAndWidth(it) }.toIntArray()
        repeat(minOf(12, POPULATION_SIZE / 4)) {
            pop.add(strictByWindow.copyOf())
        }

        while (pop.size < POPULATION_SIZE) {
            pop.add(greedyNearestNeighbor(orders, startLat, startLon, startZdt))
        }
        for (c in pop) {
            repairWindowOrder(c, orders, startZdt)
        }
        return pop
    }

    private fun greedyNearestNeighbor(
        orders: List<OptOrder>,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
    ): IntArray {
        val numOrders = orders.size
        val remaining = (0 until numOrders).toMutableSet()
        val chrom = mutableListOf<Int>()
        var curLat = startLat
        var curLon = startLon
        var curTime = startZdt
        val orderDate = startZdt.toLocalDate()
        val zone = startZdt.zone
        while (remaining.isNotEmpty()) {
            var minEndTs = Long.MAX_VALUE
            for (idx in remaining) {
                val o = orders[idx]
                if (o.windowEnd != null) {
                    val ts = ZonedDateTime.of(orderDate, o.windowEnd, zone).toEpochSecond()
                    if (ts < minEndTs) minEndTs = ts
                }
            }
            val candidates = remaining.filter { idx ->
                val o = orders[idx]
                o.windowEnd == null ||
                    ZonedDateTime.of(orderDate, o.windowEnd, zone).toEpochSecond() <= minEndTs
            }.ifEmpty { remaining.toList() }

            var bestIdx: Int? = null
            var bestScore = Pair(Double.POSITIVE_INFINITY, Long.MAX_VALUE)
            var bestDist = 0.0
            for (idx in candidates) {
                val o = orders[idx]
                val dist = Haversine.distanceKm(curLat, curLon, o.lat, o.lon)
                val travelEst = dist / GREEDY_EST_KM_PER_MIN
                var arrivalEst = curTime.plusMinutesFp(travelEst)
                var latePen = 0.0
                if (o.windowEnd != null) {
                    val we = ZonedDateTime.of(orderDate, o.windowEnd, zone)
                    if (arrivalEst > we) latePen = 1e6
                }
                val endTs = o.windowEnd?.let { ZonedDateTime.of(orderDate, it, zone).toEpochSecond() } ?: Long.MAX_VALUE
                val score = latePen + dist to endTs
                if (score.first < bestScore.first || (score.first == bestScore.first && score.second < bestScore.second)) {
                    bestScore = score
                    bestIdx = idx
                    bestDist = dist
                }
            }
            val idx = bestIdx!!
            val o = orders[idx]
            chrom.add(idx)
            remaining.remove(idx)
            curLat = o.lat
            curLon = o.lon
            val travelEst = bestDist / GREEDY_EST_KM_PER_MIN
            var arrivalEst = curTime.plusMinutesFp(travelEst)
            if (o.windowStart != null && o.windowEnd != null) {
                val ws = ZonedDateTime.of(orderDate, o.windowStart, zone)
                if (arrivalEst < ws) arrivalEst = ws
            }
            curTime = arrivalEst.plusMinutesFp(serviceMin)
        }
        return chrom.toIntArray()
    }

    private fun fitness(
        chromosome: IntArray,
        orders: List<OptOrder>,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
    ): Double {
        if (chromosome.isEmpty()) return Double.POSITIVE_INFINITY
        val orderDate = startZdt.toLocalDate()
        val zone = startZdt.zone
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
                    violations++
                    val delay = ChronoUnit.NANOS.between(windowEnd, arrival) / 60_000_000_000.0
                    if (delay > MAX_DELAY_MINUTES) {
                        criticalDelays++
                        criticalDelayMinutes += delay
                        totalDelay += delay
                    } else {
                        totalDelay += delay
                    }
                }
            }
            order.manualArrival?.let { manual ->
                val diffMin = abs(ChronoUnit.NANOS.between(manual, arrival)) / 60_000_000_000.0
                if (diffMin > MANUAL_TIME_TOLERANCE) manualViolations++
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

    private fun tournamentSelection(population: List<IntArray>, fitnessScores: List<Double>): IntArray {
        val idxs = rng.sampleRange(population.size, TOURNAMENT_SIZE)
        var bestT = 0
        var bestF = fitnessScores[idxs[0]]
        for (t in 1 until idxs.size) {
            val j = idxs[t]
            if (fitnessScores[j] < bestF) {
                bestF = fitnessScores[j]
                bestT = t
            }
        }
        return population[idxs[bestT]].copyOf()
    }

    private fun repairWindowOrder(chromosome: IntArray, orders: List<OptOrder>, startZdt: ZonedDateTime) {
        if (chromosome.size < 2) return
        val orderDate = startZdt.toLocalDate()
        val zone = startZdt.zone
        val thresholdZdt = ZonedDateTime.of(orderDate, EARLY_WINDOW_END, zone)
        val n = chromosome.size
        while (true) {
            var swapped = false
            for (i in 0 until n - 1) {
                val oi = orders[chromosome[i]]
                val oj = orders[chromosome[i + 1]]
                val wei = oi.windowEnd
                val wej = oj.windowEnd
                if (wei == null || wej == null) continue
                val weIZdt = ZonedDateTime.of(orderDate, wei, zone)
                val weJZdt = ZonedDateTime.of(orderDate, wej, zone)
                if (weIZdt > weJZdt && weJZdt <= thresholdZdt) {
                    val t = chromosome[i]
                    chromosome[i] = chromosome[i + 1]
                    chromosome[i + 1] = t
                    swapped = true
                }
            }
            if (!swapped) break
        }
    }

    private fun orderCrossover(p1: IntArray, p2: IntArray): IntArray {
        if (p1.size != p2.size) return p1.copyOf()
        val n = p1.size
        if (n <= 2) return p1.copyOf()
        val start = rng.randInt(0, n - 2)
        val end = rng.randInt(start + 1, n - 1)
        val child = arrayOfNulls<Int>(n)
        for (i in start..end) child[i] = p1[i]
        val used = (start..end).map { p1[it] }.toMutableSet()
        var idx = (end + 1) % n
        for (v in p2) {
            if (v !in used) {
                while (child[idx] != null) {
                    idx = (idx + 1) % n
                    if (idx == start) idx = (idx + 1) % n
                }
                child[idx] = v
                idx = (idx + 1) % n
                if (idx == start) idx = (idx + 1) % n
            }
        }
        if (child.any { it == null }) {
            return IntArray(n) { i -> child[i] ?: (n + 1) }
        }
        return IntArray(n) { child[it]!! }
    }

    private fun mutate(chromosome: IntArray, orders: List<OptOrder>, startZdt: ZonedDateTime): IntArray {
        if (chromosome.size <= 1) return chromosome.copyOf()
        val t = rng.random()
        if (t < 0.1 && orders.isNotEmpty()) {
            return smartMutationForDelays(chromosome, orders, startZdt)
        }
        if (t < 0.5) {
            val p = rng.sampleRange(chromosome.size, 2)
            val i = p[0]
            val j = p[1]
            val m = chromosome.copyOf()
            val tmp = m[i]
            m[i] = m[j]
            m[j] = tmp
            return m
        }
        if (t < 0.8) {
            val m = chromosome.copyOf()
            val st = rng.randInt(0, m.size - 2)
            val en = rng.randInt(st + 1, m.size - 1)
            var i = st
            var j = en
            while (i < j) {
                val tmp = m[i]
                m[i] = m[j]
                m[j] = tmp
                i++
                j--
            }
            return m
        }
        val m = chromosome.toMutableList()
        val idx = rng.randInt(0, m.size - 1)
        val v = m.removeAt(idx)
        val ni = rng.randInt(0, m.size)
        m.add(ni, v)
        return m.toIntArray()
    }

    private fun smartMutationForDelays(chromosome: IntArray, orders: List<OptOrder>, startZdt: ZonedDateTime): IntArray {
        val mutated = chromosome.toMutableList()
        val orderDate = startZdt.toLocalDate()
        val zone = startZdt.zone
        val half = chromosome.size / 2.0
        val lateRoute = mutableListOf<Triple<Int, ZonedDateTime, Int>>()
        for ((pos, gene) in chromosome.withIndex()) {
            if (pos > half && gene < orders.size) {
                val o = orders[gene]
                if (o.windowEnd != null) {
                    val we = ZonedDateTime.of(orderDate, o.windowEnd, zone)
                    lateRoute.add(Triple(gene, we, pos))
                }
            }
        }
        if (lateRoute.isNotEmpty()) {
            lateRoute.sortWith(compareByDescending<Triple<Int, ZonedDateTime, Int>> { it.third }.thenBy { it.second.toEpochSecond() })
            for ((orderIdx, _, _) in lateRoute.take(minOf(2, lateRoute.size))) {
                val mp = mutated.indexOf(orderIdx)
                if (mp >= 0) {
                    mutated.removeAt(mp)
                    val newPos = if (mutated.size > 2) {
                        rng.randInt(2, maxOf(3, chromosome.size / 3))
                    } else {
                        rng.randInt(0, mutated.size)
                    }
                    mutated.add(newPos.coerceIn(0, mutated.size), orderIdx)
                }
            }
        }
        return mutated.toIntArray()
    }

    private fun isValidChromosome(chromosome: IntArray, numOrders: Int): Boolean {
        if (chromosome.size != numOrders) return false
        val set = chromosome.toSet()
        return set.size == numOrders && (0 until numOrders).all { it in set }
    }

    private fun buildRouteFromChromosome(
        chromosome: IntArray,
        orders: List<OptOrder>,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
    ): GRoute {
        val points = mutableListOf<GPoint>()
        var totalDistance = 0.0
        var totalTime = 0.0
        var curLat = startLat
        var curLon = startLon
        var curTime = startZdt
        val orderDate = startZdt.toLocalDate()
        val zone = startZdt.zone
        for (idx in chromosome) {
            if (idx !in orders.indices) continue
            val order = orders[idx]
            val (dist, travelMin) = try {
                maps.getRouteSync(curLat, curLon, order.lat, order.lon)
            } catch (_: Exception) {
                continue
            }
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
                        if (arrival < curTime) arrival = curTime
                    }
                }
            }
            val ws = order.windowStart
            val we = order.windowEnd
            if (ws != null && we != null) {
                val windowStart = ZonedDateTime.of(orderDate, ws, zone)
                if (arrival < windowStart) arrival = windowStart
            }
            points.add(GPoint(order, arrival, dist, travelMin))
            totalDistance += dist
            totalTime += travelMin + serviceMin
            curLat = order.lat
            curLon = order.lon
            curTime = arrival.plusMinutesFp(serviceMin)
        }
        return GRoute(points, totalDistance, totalTime, curTime)
    }

    private fun recalculateRouteTimes(
        pointsList: List<GPoint>,
        orders: List<OptOrder>,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
    ): GRoute? {
        if (pointsList.isEmpty()) return null
        val orderDate = startZdt.toLocalDate()
        val zone = startZdt.zone
        val out = mutableListOf<GPoint>()
        var totalDistance = 0.0
        var totalTime = 0.0
        var curLat = startLat
        var curLon = startLon
        var curTime = startZdt
        for (point in pointsList) {
            val order = point.order
            val (dist, travelMin) = try {
                maps.getRouteSync(curLat, curLon, order.lat, order.lon)
            } catch (_: Exception) {
                return null
            }
            var arrival = curTime.plusMinutesFp(travelMin)
            if (order.windowStart != null && order.windowEnd != null) {
                val ws = ZonedDateTime.of(orderDate, order.windowStart, zone)
                if (arrival < ws) arrival = ws
            }
            out.add(GPoint(order, arrival, dist, travelMin))
            totalDistance += dist
            totalTime += travelMin + serviceMin
            curLat = order.lat
            curLon = order.lon
            curTime = arrival.plusMinutesFp(serviceMin)
        }
        return GRoute(out, totalDistance, totalTime, curTime)
    }

    private fun routeDelayStats(route: GRoute, orderDate: LocalDate, zone: java.time.ZoneId): Triple<Double, Int, Boolean> {
        var total = 0.0
        var count = 0
        var critical = false
        for (p in route.points) {
            val o = p.order
            if (o.windowStart == null || o.windowEnd == null) continue
            val we = ZonedDateTime.of(orderDate, o.windowEnd, zone)
            val tolNanos = (WINDOW_END_TOLERANCE_MINUTES * 60_000_000_000L).toLong()
            if (p.arrival <= we.plusNanos(tolNanos)) continue
            val d = ChronoUnit.NANOS.between(we, p.arrival) / 60_000_000_000.0
            total += d
            count++
            if (d > MAX_DELAY_MINUTES) critical = true
        }
        return Triple(total, count, critical)
    }

    private fun polishRouteByDistance(
        route: GRoute,
        orders: List<OptOrder>,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
    ): GRoute {
        if (route.points.size < 2) return route
        val orderDate = startZdt.toLocalDate()
        val zone = startZdt.zone
        var pointsList = route.points.toMutableList()
        var improved = true
        while (improved) {
            improved = false
            val current = recalculateRouteTimes(pointsList, orders, maps, startLat, startLon, startZdt) ?: break
            val (totalDelay, countDelay, hasCrit) = routeDelayStats(current, orderDate, zone)
            if (countDelay > 0 || hasCrit) break
            val distNow = current.totalDistance
            for (i in 0 until pointsList.size - 1) {
                val oi = pointsList[i].order
                val oj = pointsList[i + 1].order
                if (oi.windowEnd == null || oj.windowEnd == null) continue
                val weI = ZonedDateTime.of(orderDate, oi.windowEnd, zone)
                val weJ = ZonedDateTime.of(orderDate, oj.windowEnd, zone)
                if (weI != weJ) continue
                val swapped = pointsList.toMutableList()
                val tmp = swapped[i]
                swapped[i] = swapped[i + 1]
                swapped[i + 1] = tmp
                val trial = recalculateRouteTimes(swapped, orders, maps, startLat, startLon, startZdt) ?: continue
                if (trial.totalDistance >= distNow) continue
                val (tTot, tCnt, tCrit) = routeDelayStats(trial, orderDate, zone)
                if (tCnt > 0 || tCrit) continue
                pointsList = swapped
                improved = true
                break
            }
        }
        return recalculateRouteTimes(pointsList, orders, maps, startLat, startLon, startZdt) ?: route
    }

    private fun toOutputJson(route: GRoute, orderDate: LocalDate, zone: java.time.ZoneId): ParityOptimizeOutputJson {
        val outs = route.points.map { p ->
            val we = p.order.windowEnd
            val windowEndZdt = if (we != null) ZonedDateTime.of(orderDate, we, zone) else null
            val isLate = windowEndZdt != null && p.arrival > windowEndZdt
            RoutePointOutJson(
                orderNumber = p.order.orderNumber,
                estimatedArrivalIso = p.arrival.truncatedTo(ChronoUnit.SECONDS).format(pythonIso),
                distanceFromPreviousKm = p.distanceFromPrev,
                timeFromPreviousMin = p.timeFromPrev,
                isLate = isLate,
                windowStart = p.order.windowStart?.format(windowHhMm),
                windowEnd = p.order.windowEnd?.format(windowHhMm),
            )
        }
        return ParityOptimizeOutputJson(
            routePoints = outs,
            totalDistanceKm = route.totalDistance,
            totalTimeMin = route.totalTime,
            estimatedCompletionIso = route.completion.truncatedTo(ChronoUnit.SECONDS).format(pythonIso),
        )
    }

    private fun ZonedDateTime.plusMinutesFp(minutes: Double): ZonedDateTime {
        val nanos = (minutes * 60_000_000_000.0).roundToLong()
        return this.plusNanos(nanos)
    }
}
