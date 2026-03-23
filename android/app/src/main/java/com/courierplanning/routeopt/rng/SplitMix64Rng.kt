package com.courierplanning.routeopt.rng

/**
 * SplitMix64 — детерминированный PRNG, тот же алгоритм, что используется для golden-экспорта
 * с тем же seed, что и Python [SplitMix64Rng] (см. `src/services/genetic_rng.py` при наличии).
 *
 * API под операции Python `random`: [random] ≈ random.random(), [randIntInclusive] ≈ random.randint.
 */
class SplitMix64Rng(seed: ULong) {
    private var state: ULong = seed

    fun nextULong(): ULong {
        state += 0x9E3779B97F4A7C15UL
        var z = state
        z = (z xor (z shr 30)) * 0xBF58476D1CE4E5B9UL
        z = (z xor (z shr 27)) * 0x94D049BB133111EBUL
        return z xor (z shr 31)
    }

    /** [0.0, 1.0) как у random.random() */
    fun random(): Double {
        val x = nextULong() ushr 11
        return x.toDouble() / (1L shl 53).toDouble()
    }

    /** Включительно [lo, hi], как random.randint(lo, hi). */
    fun randIntInclusive(lo: Int, hi: Int): Int {
        require(lo <= hi) { "lo=$lo hi=$hi" }
        val span = hi.toLong() - lo.toLong() + 1L
        val u = nextULong()
        val mod = (u % span.toULong()).toLong()
        return lo + mod.toInt()
    }

    fun shuffle(list: MutableList<Int>) {
        for (i in list.lastIndex downTo 1) {
            val j = randIntInclusive(0, i)
            val t = list[i]
            list[i] = list[j]
            list[j] = t
        }
    }

    /**
     * Как random.sample(range(n), k): k различных индексов из [0, n).
     */
    fun sampleDistinctIndices(n: Int, k: Int): List<Int> {
        require(k in 0..n) { "n=$n k=$k" }
        val pool = (0 until n).toMutableList()
        shuffle(pool)
        return pool.take(k)
    }
}
