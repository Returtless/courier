package com.courierplanning.routeopt.genetic

import com.courierplanning.routeopt.core.MatrixRoutingAdapter
import com.courierplanning.routeopt.parity.MatrixParityOptimizer
import com.courierplanning.routeopt.parity.MatrixParityOptimizer.InternalOrder
import com.courierplanning.routeopt.parity.ParityOptimizeOutputJson
import java.time.LocalTime
import java.time.ZonedDateTime
import java.time.temporal.ChronoUnit
import kotlin.random.Random

/**
 * Генетика в духе Python [GeneticRouteOptimizer] для N > exhaustive: элитизм, OX, мутации, repair окон.
 * RNG: [kotlin.random.Random] (не byte-parity с Python SplitMix; для прод-маршрутов с OSRM-матрицей).
 */
class KotlinGeneticRouteOptimizer(
    seed: Int,
    private val serviceMin: Double,
) {
    private val rng = Random(seed.toLong())

    private companion object {
        const val POPULATION_SIZE = 80
        const val MAX_GENERATIONS = 200
        const val TOURNAMENT_SIZE = 3
        const val CROSSOVER_RATE = 0.8
        const val MUTATION_RATE = 0.2
        const val ELITISM_COUNT = 10
        private val EARLY_END: LocalTime = LocalTime.of(13, 0)
    }

    fun optimize(
        orders: List<InternalOrder>,
        maps: MatrixRoutingAdapter,
        startLat: Double,
        startLon: Double,
        startZdt: ZonedDateTime,
    ): ParityOptimizeOutputJson {
        val zone = startZdt.zone
        val orderDate = startZdt.toLocalDate()
        val n = orders.size
        if (n == 0) {
            return ParityOptimizeOutputJson(
                routePoints = emptyList(),
                totalDistanceKm = 0.0,
                totalTimeMin = 0.0,
                estimatedCompletionIso = startZdt.truncatedTo(ChronoUnit.SECONDS)
                    .format(java.time.format.DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ssXXX").withLocale(java.util.Locale.ROOT)),
            )
        }
        if (n == 1) {
            val route = MatrixParityOptimizer.buildRouteFromChromosome(
                intArrayOf(0), orders, maps, startLat, startLon, startZdt, orderDate, zone, serviceMin,
            )
            return MatrixParityOptimizer.toOutputJson(route, orderDate, zone)
        }

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
                val child = if (rng.nextDouble() < CROSSOVER_RATE) orderCrossover(p1, p2) else {
                    if (rng.nextDouble() < 0.5) p1.copyOf() else p2.copyOf()
                }
                val mutated = if (rng.nextDouble() < MUTATION_RATE) mutate(child, n) else child
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
        return MatrixParityOptimizer.toOutputJson(route, orderDate, zone)
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
            val m = (0 until numOrders).shuffled(rng).toIntArray()
            pop.add(m)
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
                group.shuffle(rng)
                chrom.addAll(group)
            }
            pop.add(chrom.toIntArray())
        }
        while (pop.size < POPULATION_SIZE) {
            pop.add((0 until numOrders).shuffled(rng).toIntArray())
        }
        for (c in pop) repairWindowOrder(c, orders, startZdt)
        return pop
    }

    private fun tournamentSelection(population: List<IntArray>, fitnessScores: List<Double>): IntArray {
        val idxs = List(TOURNAMENT_SIZE) { rng.nextInt(population.size) }
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

    /** Order crossover (OX): сегмент из p1, остальное — в порядке обхода p2, без «дыр». */
    private fun orderCrossover(p1: IntArray, p2: IntArray): IntArray {
        if (p1.size != p2.size) return p1.copyOf()
        val n = p1.size
        if (n <= 2) return p1.copyOf()
        val a = rng.nextInt(n)
        val b = rng.nextInt(n)
        val start = minOf(a, b)
        val end = maxOf(a, b)
        if (start == end) return p1.copyOf()
        val child = IntArray(n) { -1 }
        val inSlice = BooleanArray(n)
        for (k in start..end) {
            child[k] = p1[k]
            inSlice[p1[k]] = true
        }
        var idx = (end + 1) % n
        for (x in p2) {
            if (inSlice[x]) continue
            while (child[idx] != -1) idx = (idx + 1) % n
            child[idx] = x
            idx = (idx + 1) % n
        }
        return child
    }

    private fun mutate(chromosome: IntArray, n: Int): IntArray {
        if (n <= 1) return chromosome.copyOf()
        val t = rng.nextDouble()
        if (t < 0.5) {
            val i = rng.nextInt(n)
            val j = rng.nextInt(n)
            val m = chromosome.copyOf()
            val tmp = m[i]
            m[i] = m[j]
            m[j] = tmp
            return m
        }
        if (t < 0.8 && n >= 2) {
            val m = chromosome.copyOf()
            val st = rng.nextInt(n - 1)
            val en = rng.nextInt(st + 1, n)
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
        val idx = rng.nextInt(list.size)
        val v = list.removeAt(idx)
        list.add(rng.nextInt(list.size + 1), v)
        return list.toIntArray()
    }

    private fun isValidChromosome(chromosome: IntArray, numOrders: Int): Boolean {
        if (chromosome.size != numOrders) return false
        val set = chromosome.toSet()
        return set.size == numOrders && (0 until numOrders).all { it in set }
    }
}
