package com.courierplanning.routeopt.rng

/**
 * Deterministic PRNG matching [src.services.genetic_rng.SplitMix64Rng] (Python uses arbitrary precision; we use UInt128 via ULong mod 2^64).
 */
class SplitMix64Rng(seed: Int) {
    private var state: ULong = (seed.toULong() and ULong.MAX_VALUE).let { if (it == 0uL) 0x9E3779B97F4A7C15uL else it }

    private fun nextU64(): ULong {
        var z = state + 0x9E3779B97F4A7C15uL
        state = z
        z = (z xor (z shr 30)) * 0xBF58476D1CE4E5B9uL
        z = (z xor (z shr 27)) * 0x94D049BB133111EBuL
        return z xor (z shr 31)
    }

    /** [0.0, 1.0) */
    fun random(): Double {
        val u = (nextU64() shr 11).toLong() and ((1L shl 53) - 1)
        return u.toDouble() * (1.0 / (1L shl 53))
    }

    /** Inclusive a..b */
    fun randInt(a: Int, b: Int): Int {
        var lo = a
        var hi = b
        if (lo > hi) {
            val t = lo
            lo = hi
            hi = t
        }
        val span = hi.toLong() - lo.toLong() + 1L
        if (span <= 0L) return lo
        val u = nextU64()
        val r = (u % span.toULong()).toLong()
        return lo + r.toInt()
    }

    fun shuffle(list: MutableList<*>) {
        for (i in list.lastIndex downTo 1) {
            val j = randInt(0, i)
            @Suppress("UNCHECKED_CAST")
            val l = list as MutableList<Any?>
            val t = l[i]
            l[i] = l[j]
            l[j] = t
        }
    }

    /** k distinct indices from [0, n) */
    fun sampleRange(n: Int, k: Int): IntArray {
        require(k in 0..n) { "sampleRange n=$n k=$k" }
        val arr = IntArray(n) { it }
        for (i in n - 1 downTo 1) {
            val j = randInt(0, i)
            val t = arr[i]
            arr[i] = arr[j]
            arr[j] = t
        }
        return arr.copyOf(k)
    }
}
