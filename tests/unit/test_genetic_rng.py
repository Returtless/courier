"""SplitMix64Rng determinism (parity with Kotlin)."""
from src.services.genetic_rng import SplitMix64Rng


def test_splitmix_same_sequence_for_seed():
    a = SplitMix64Rng(42)
    b = SplitMix64Rng(42)
    for _ in range(50):
        assert a.random() == b.random()


def test_splitmix_seed_zero_uses_nonzero_state():
    r = SplitMix64Rng(0)
    assert 0.0 <= r.random() < 1.0
