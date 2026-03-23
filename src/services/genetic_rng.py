"""
Детерминированный SplitMix64 — тот же алгоритм, что Kotlin [SplitMix64Rng].
Используется в tools/export_optimizer_golden.py для совпадения golden с JVM.
"""
from __future__ import annotations

from typing import Any, List, MutableSequence, Sequence, TypeVar


class SplitMix64Rng:
    def __init__(self, seed: int) -> None:
        self._state = seed & ((1 << 64) - 1)

    def next_u64(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
        z = self._state
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9 & ((1 << 64) - 1)
        z = (z ^ (z >> 27)) * 0x94D049BB133111EB & ((1 << 64) - 1)
        return (z ^ (z >> 31)) & ((1 << 64) - 1)

    def random(self) -> float:
        x = self.next_u64() >> 11
        return x / float(1 << 53)

    def randint(self, a: int, b: int) -> int:
        if a > b:
            raise ValueError("empty range")
        span = b - a + 1
        return a + (self.next_u64() % span)

    def shuffle(self, x: MutableSequence[Any]) -> None:
        for i in range(len(x) - 1, 0, -1):
            j = self.randint(0, i)
            x[i], x[j] = x[j], x[i]

    def sample(self, population: Sequence[Any], k: int, *, counts: Any = None) -> List[Any]:
        if counts is not None:
            raise NotImplementedError
        n = len(population)
        if k > n:
            raise ValueError("Sample larger than population")
        indices = list(range(n))
        self.shuffle(indices)
        return [population[i] for i in indices[:k]]


_T = TypeVar("_T")


def patch_random_module(rng: SplitMix64Rng) -> None:
    """Подменяет random.* для вызовов из GeneticRouteOptimizer при экспорте golden."""
    import random as R

    R.random = rng.random  # type: ignore[assignment]
    R.randint = rng.randint  # type: ignore[assignment]
    R.shuffle = rng.shuffle  # type: ignore[assignment]
    R.sample = rng.sample  # type: ignore[assignment]
    # GeneticRouteOptimizer.__init__ вызывает random.seed() — не сбрасывать SplitMix.
    R.seed = lambda *args, **kwargs: None  # type: ignore[assignment]
