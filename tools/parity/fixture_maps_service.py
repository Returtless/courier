"""
In-memory MapsService for parity tests: routes from JSON matrix only (no HTTP, no DB).

Fixture format (see parity_fixtures/*/input.json):
- nodes: [ { "lat", "lon" }, ... ] index 0 = start, 1..n = orders in the same order as `orders`
- route_matrix: { "i,j": { "distance_km": float, "travel_min": float }, ... }
  Keys use comma between indices. All directed pairs that the optimizer may query should be present.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _round5(x: float) -> float:
    return round(float(x), 5)


class ParityMapsService:
    """Drop-in replacement for MapsService in GeneticRouteOptimizer parity runs."""

    def __init__(self, nodes: List[Dict[str, Any]], route_matrix: Dict[str, Dict[str, float]]):
        self._nodes = nodes
        self._matrix = route_matrix
        self._coord_to_idx: Dict[Tuple[float, float], int] = {}
        for i, n in enumerate(nodes):
            la = _round5(n["lat"])
            lo = _round5(n["lon"])
            self._coord_to_idx[(la, lo)] = i

    def _lookup_indices(
        self, start_lat: float, start_lon: float, end_lat: float, end_lon: float
    ) -> Tuple[int, int]:
        sa, so = _round5(start_lat), _round5(start_lon)
        ea, eo = _round5(end_lat), _round5(end_lon)
        i = self._coord_to_idx.get((sa, so))
        j = self._coord_to_idx.get((ea, eo))
        if i is None or j is None:
            raise KeyError(
                f"ParityMapsService: unknown node "
                f"({start_lat},{start_lon})->({end_lat},{end_lon}) "
                f"(rounded ({sa},{so})->({ea},{eo})); known={self._coord_to_idx}"
            )
        return i, j

    def get_route_sync(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        user_id: Optional[int] = None,
    ) -> Tuple[float, float]:
        i, j = self._lookup_indices(start_lat, start_lon, end_lat, end_lon)
        key = f"{i},{j}"
        cell = self._matrix.get(key)
        if cell is None:
            raise KeyError(f"ParityMapsService: missing matrix key {key!r} for edge {i}->{j}")
        dk = float(cell["distance_km"])
        tm = float(cell["travel_min"])
        return dk, tm

    def geocode_address_sync(self, address: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """Parity fixtures must include lat/lon on orders; no network geocode."""
        _ = address
        return None, None, None
