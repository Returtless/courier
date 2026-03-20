"""
Deterministic PRNG for GeneticRouteOptimizer parity (Python + Kotlin must match).

SplitMix64-style mixing; shuffle/randint/sample mirror the algorithms used from Kotlin.
"""
from __future__ import annotations

from typing import Any, List, MutableSequence, Optional


class SplitMix64Rng:
    """64-bit state; same nextDouble/nextInt/shuffle semantics as Kotlin [SplitMix64Rng]."""

    MASK64 = (1 << 64) - 1

    def __init__(self, seed: int) -> None:
        s = int(seed) & self.MASK64
        self._state = s if s != 0 else 0x9E3779B97F4A7C15

    def _next_u64(self) -> int:
        z = (self._state + 0x9E3779B97F4A7C15) & self.MASK64
        self._state = z
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9 & self.MASK64
        z = (z ^ (z >> 27)) * 0x94D049BB133111EB & self.MASK64
        return (z ^ (z >> 31)) & self.MASK64

    def random(self) -> float:
        """[0.0, 1.0) matching Kotlin nextDouble."""
        u = self._next_u64() >> 11
        return u * (1.0 / (1 << 53))

    def rand_int(self, a: int, b: int) -> int:
        """Inclusive a..b (Kotlin nextInt)."""
        if a > b:
            a, b = b, a
        span = b - a + 1
        if span <= 0:
            return a
        # Rejection to avoid modulo bias for large spans (same idea as Kotlin)
        u = self._next_u64()
        r = u % span
        return a + int(r)

    def shuffle(self, x: MutableSequence[Any]) -> None:
        """Same loop as Kotlin: i from lastIndex downTo 1."""
        n = len(x)
        for i in range(n - 1, 0, -1):
            j = self.rand_int(0, i)
            x[i], x[j] = x[j], x[i]

    def sample_range(self, n: int, k: int) -> List[int]:
        """k distinct indices from [0, n), order not sorted."""
        if k > n or k < 0:
            raise ValueError("sample_range invalid k")
        arr = list(range(n))
        self.shuffle(arr)
        return arr[:k]


class PythonStdRandomAdapter:
    """Delegates to global `random` module (production default)."""

    def __init__(self) -> None:
        import random as _r

        self._r = _r

    def random(self) -> float:
        return self._r.random()

    def rand_int(self, a: int, b: int) -> int:
        return self._r.randint(a, b)

    def shuffle(self, x: MutableSequence[Any]) -> None:
        self._r.shuffle(x)

    def sample_range(self, n: int, k: int) -> List[int]:
        return list(self._r.sample(range(n), k))


def make_rng_for_seed(seed: Optional[int]) -> Any:
    if seed is None:
        return PythonStdRandomAdapter()
    return SplitMix64Rng(int(seed))
