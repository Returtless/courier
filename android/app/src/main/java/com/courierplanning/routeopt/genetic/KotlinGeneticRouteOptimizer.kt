package com.courierplanning.routeopt.genetic

import com.courierplanning.routeopt.core.MatrixRoutingAdapter
import com.courierplanning.routeopt.math.Haversine
import com.courierplanning.routeopt.parity.MatrixParityOptimizer
import com.courierplanning.routeopt.parity.MatrixParityOptimizer.InternalOrder
import com.courierplanning.routeopt.parity.ParityOptimizeOutputJson
import com.courierplanning.routeopt.rng.SplitMix64Rng
import java.time.LocalTime
import java.time.ZonedDateTime
import java.time.temporal.ChronoUnit
import kotlin.math.roundToLong

/**
 * Порт цикла [src.services.route_optimizer_genetic.GeneticRouteOptimizer] (ветка без OR-Tools).
 * RNG: [SplitMix64Rng] с seed из JSON — детерминированно; соответствует golden-экспорту при том же seed на Python.
 */
class KotlinGeneticRouteOptimizer(
    seed: Int,
    private val serviceMin: Double,
) {
    private val rng = SplitMix64Rng(seed.toUInt().toULong())

    private companion object {
        const val POPULATION_SIZE = 80
        const val MAX_GENERATIONS = 200
        const val TOURNAMENT_SIZE = 3
        const val CROSSOVER_RATE = 0.8
        const val MUTATION_RATE = 0.2
        const val ELITISM_COUNT = 10
        private val EARLY_END: LocalTime = LocalTime.of(13, 0)
    }

    /**
     * Только для N≥2 (как [_genetic_algorithm] в Python). Пустой список и один заказ — обрабатывает [MatrixParityOptimizer].
     */
    fun optimize(
        orders: List<InternalOrder>,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
    ): ParityOptimizeOutputJson {
        require(orders.size >= 2) { "GA: ожидается ≥2 заказов" }
        val zone = startZdt.zone
        val orderDate = startZdt.toLocalDate()
        val n = orders.size

        var population = generateInitialPopulation(orders, startLat, startLon, startZdt)
        var fitnessScores = population.map {
            MatrixParityOptimizer.fitness(it, orders, maps, startLat, startLon, startZdt, orderDate, zone, serviceMin)
        }
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
                val mutated = if (rng.random() < MUTATION_RATE) mutate(child, n, orders, startZdt) else child
                repairWindowOrder(mutated, orders, startZdt)
                if (isValidChromosome(mutated, n)) newPop.add(mutated)
            }
            population = newPop
            fitnessScores = population.map {
                MatrixParityOptimizer.fitness(it, orders, maps, startLat, startLon, startZdt, orderDate, zone, serviceMin)
            }
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
        val route = MatrixParityOptimizer.buildRouteFromChromosome(
            bestChromosome, orders, maps, startLat, startLon, startZdt, orderDate, zone, serviceMin,
        )
        val finished = GeneticRoutePostProcessor.applyBotPostProcess(
            route, maps, startLat, startLon, startZdt, serviceMin,
        )
        return MatrixParityOptimizer.toOutputJson(finished, orderDate, zone)
    }

    private fun generateInitialPopulation(
        orders: List<InternalOrder>,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
    ): List<IntArray> {
        val numOrders = orders.size
        val pop = mutableListOf<IntArray>()
        val orderDate = startZdt.toLocalDate()
        val zone = startZdt.zone
        repeat(POPULATION_SIZE / 4) {
            val m = (0 until numOrders).toMutableList()
            rng.shuffle(m)
            pop.add(m.toIntArray())
        }
        val indicesByEnd = mutableMapOf<Long, MutableList<Int>>()
        for (i in 0 until numOrders) {
            val o = orders[i]
            val k = o.windowEnd?.let { ZonedDateTime.of(orderDate, it, zone).toEpochSecond() } ?: Long.MAX_VALUE
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
            val sortedIndices = (0 until numOrders).sortedBy { i ->
                orders[i].windowStart?.let { ZonedDateTime.of(orderDate, it, zone).toEpochSecond() }
                    ?: Long.MAX_VALUE
            }.toMutableList()
            repeat(rng.randIntInclusive(0, numOrders / 3)) {
                val pair = rng.sampleDistinctIndices(numOrders, 2)
                val i = pair[0]
                val j = pair[1]
                val t = sortedIndices[i]
                sortedIndices[i] = sortedIndices[j]
                sortedIndices[j] = t
            }
            pop.add(sortedIndices.toIntArray())
        }
        fun endAndWidthKey(i: Int): Pair<Long, Long> {
            val o = orders[i]
            val we = o.windowEnd ?: return Long.MAX_VALUE to 0L
            val endTs = ZonedDateTime.of(orderDate, we, zone).toEpochSecond()
            if (o.windowStart == null) return endTs to 0L
            val durMin = ChronoUnit.MINUTES.between(
                ZonedDateTime.of(orderDate, o.windowStart!!, zone),
                ZonedDateTime.of(orderDate, we, zone),
            )
            return endTs to -durMin
        }
        repeat(POPULATION_SIZE / 8) {
            val chrom = (0 until numOrders).sortedBy { endAndWidthKey(it) }.toMutableList()
            repeat(rng.randIntInclusive(0, numOrders / 4)) {
                val pair = rng.sampleDistinctIndices(numOrders, 2)
                val i = pair[0]
                val j = pair[1]
                val t = chrom[i]
                chrom[i] = chrom[j]
                chrom[j] = t
            }
            pop.add(chrom.toIntArray())
        }
        val strictByWindow = (0 until numOrders).sortedBy { endAndWidthKey(it) }.toIntArray()
        repeat(minOf(12, POPULATION_SIZE / 4)) {
            pop.add(strictByWindow.copyOf())
        }
        while (pop.size < POPULATION_SIZE) {
            pop.add(greedyNearestNeighborChromosome(orders, startLat, startLon, startZdt))
        }
        for (c in pop) repairWindowOrder(c, orders, startZdt)
        return pop
    }

    private fun greedyNearestNeighborChromosome(
        orders: List<InternalOrder>,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
    ): IntArray {
        val numOrders = orders.size
        if (numOrders == 0) return intArrayOf()
        val orderDate = startZdt.toLocalDate()
        val zone = startZdt.zone
        val greedyEstKmPerMin = 0.5
        val chrom = mutableListOf<Int>()
        val remaining = (0 until numOrders).toMutableSet()
        var curLat = startLat
        var curLon = startLon
        var curTime = startZdt
        while (remaining.isNotEmpty()) {
            var minWindowEndTs = Double.POSITIVE_INFINITY
            for (idx in remaining) {
                orders[idx].windowEnd?.let {
                    val ts = ZonedDateTime.of(orderDate, it, zone).toEpochSecond().toDouble()
                    minWindowEndTs = minOf(minWindowEndTs, ts)
                }
            }
            val candidates = if (minWindowEndTs.isFinite()) {
                remaining.filter { idx ->
                    val we = orders[idx].windowEnd
                    we == null ||
                        ZonedDateTime.of(orderDate, we, zone).toEpochSecond().toDouble() <= minWindowEndTs
                }.ifEmpty { remaining.toList() }
            } else {
                remaining.toList()
            }
            var bestIdx: Int? = null
            var bestScore = Pair(Double.POSITIVE_INFINITY, Double.POSITIVE_INFINITY)
            var bestDist = 0.0
            for (idx in candidates) {
                val order = orders[idx]
                val dist = Haversine.distanceKm(curLat, curLon, order.lat, order.lon)
                val travelEstMin = dist / greedyEstKmPerMin
                var arrivalEst = curTime.plusNanos((travelEstMin * 60_000_000_000.0).roundToLong())
                var latePenalty = 0.0
                order.windowEnd?.let { we ->
                    val weZdt = ZonedDateTime.of(orderDate, we, zone)
                    if (arrivalEst > weZdt) latePenalty = 1e6
                }
                val endTs = order.windowEnd?.let { ZonedDateTime.of(orderDate, it, zone).toEpochSecond().toDouble() }
                    ?: Double.POSITIVE_INFINITY
                val score = (latePenalty + dist) to endTs
                if (score < bestScore) {
                    bestScore = score
                    bestIdx = idx
                    bestDist = dist
                }
            }
            val pick = bestIdx ?: remaining.first()
            val order = orders[pick]
            val distLeg = if (bestIdx != null) {
                bestDist
            } else {
                Haversine.distanceKm(curLat, curLon, order.lat, order.lon)
            }
            chrom.add(pick)
            remaining.remove(pick)
            curLat = order.lat
            curLon = order.lon
            val travelEstMin = distLeg / greedyEstKmPerMin
            var arrivalEst = curTime.plusNanos((travelEstMin * 60_000_000_000.0).roundToLong())
            val ws = order.windowStart
            val we = order.windowEnd
            if (ws != null && we != null) {
                val wsZdt = ZonedDateTime.of(orderDate, ws, zone)
                if (arrivalEst < wsZdt) arrivalEst = wsZdt
            }
            curTime = arrivalEst.plusNanos((serviceMin * 60_000_000_000.0).roundToLong())
        }
        return chrom.toIntArray()
    }

    /** Как [_tournament_selection]: индексы без повторов (random.sample). */
    private fun tournamentSelection(population: List<IntArray>, fitnessScores: List<Double>): IntArray {
        val idxs = rng.sampleDistinctIndices(population.size, TOURNAMENT_SIZE)
        var bestT = idxs[0]
        var bestF = fitnessScores[bestT]
        for (t in idxs.drop(1)) {
            if (fitnessScores[t] < bestF) {
                bestF = fitnessScores[t]
                bestT = t
            }
        }
        return population[bestT].copyOf()
    }

    private fun repairWindowOrder(chromosome: IntArray, orders: List<InternalOrder>, startZdt: ZonedDateTime) {
        if (chromosome.size < 2) return
        val orderDate = startZdt.toLocalDate()
        val zone = startZdt.zone
        val thresholdZdt = ZonedDateTime.of(orderDate, EARLY_END, zone)
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

    /** Точная копия [_order_crossover] Python (OX с обходом и пропуском start). */
    private fun orderCrossover(p1: IntArray, p2: IntArray): IntArray {
        if (p1.size != p2.size) return p1.copyOf()
        val n = p1.size
        if (n <= 2) return p1.copyOf()
        val start = rng.randIntInclusive(0, n - 2)
        val end = rng.randIntInclusive(start + 1, n - 1)
        val child = arrayOfNulls<Int>(n)
        for (i in start..end) child[i] = p1[i]
        val used = (start..end).map { p1[it] }.toMutableSet()
        var idx = (end + 1) % n
        for (v in p2) {
            if (v in used) continue
            while (child[idx] != null) {
                idx = (idx + 1) % n
                if (idx == start) idx = (idx + 1) % n
            }
            child[idx] = v
            idx = (idx + 1) % n
            if (idx == start) idx = (idx + 1) % n
        }
        if (child.any { it == null }) return p1.copyOf()
        return IntArray(n) { child[it]!! }
    }

    private fun mutate(chromosome: IntArray, n: Int, orders: List<InternalOrder>, startZdt: ZonedDateTime): IntArray {
        if (n <= 1) return chromosome.copyOf()
        val u = rng.random()
        if (u < 0.1) return smartMutationForDelays(chromosome, orders, startZdt)
        if (u < 0.5) {
            val pair = rng.sampleDistinctIndices(n, 2)
            val i = pair[0]
            val j = pair[1]
            val m = chromosome.copyOf()
            val tmp = m[i]
            m[i] = m[j]
            m[j] = tmp
            return m
        }
        if (u < 0.8 && n >= 2) {
            val m = chromosome.copyOf()
            val st = rng.randIntInclusive(0, n - 2)
            val en = rng.randIntInclusive(st + 1, n - 1)
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
        val list = chromosome.toMutableList()
        val idx = rng.randIntInclusive(0, list.size - 1)
        val v = list.removeAt(idx)
        list.add(rng.randIntInclusive(0, list.size), v)
        return list.toIntArray()
    }

    private fun smartMutationForDelays(chromosome: IntArray, orders: List<InternalOrder>, startZdt: ZonedDateTime): IntArray {
        if (chromosome.size <= 1) return chromosome.copyOf()
        val orderDate = startZdt.toLocalDate()
        val zone = startZdt.zone
        val mutated = chromosome.toMutableList()
        val half = chromosome.size / 2.0
        val lateRouteOrders = mutableListOf<Triple<Int, Long, Int>>()
        for ((pos, idx) in chromosome.withIndex()) {
            if (idx !in orders.indices) continue
            if (pos <= half) continue
            val we = orders[idx].windowEnd ?: continue
            val endEpoch = ZonedDateTime.of(orderDate, we, zone).toEpochSecond()
            lateRouteOrders.add(Triple(idx, endEpoch, pos))
        }
        if (lateRouteOrders.isEmpty()) return mutated.toIntArray()
        lateRouteOrders.sortWith(
            compareByDescending<Triple<Int, Long, Int>> { it.third }
                .thenBy { it.second },
        )
        for ((orderIdx, _, _) in lateRouteOrders.take(minOf(2, lateRouteOrders.size))) {
            if (orderIdx !in mutated) continue
            val mutatedPos = mutated.indexOf(orderIdx)
            mutated.removeAt(mutatedPos)
            val upperInclusive = maxOf(3, chromosome.size / 3)
            val newPos = if (mutated.size > 2) {
                rng.randIntInclusive(2, upperInclusive).coerceAtMost(mutated.size)
            } else {
                rng.randIntInclusive(0, mutated.size)
            }
            mutated.add(newPos.coerceIn(0, mutated.size), orderIdx)
        }
        return mutated.toIntArray()
    }

    private fun isValidChromosome(chromosome: IntArray, numOrders: Int): Boolean {
        if (chromosome.size != numOrders) return false
        val set = chromosome.toSet()
        return set.size == numOrders && (0 until numOrders).all { it in set }
    }
}
