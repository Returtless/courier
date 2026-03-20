#!/usr/bin/env python3
"""Emit parity_fixtures/math_vectors/haversine.json — same formula as route_optimizer_genetic._haversine_distance."""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "parity_fixtures" / "math_vectors" / "haversine.json"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(
        dlon / 2
    ) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def main() -> None:
    cases = [
        (59.9, 30.31, 59.91, 30.32, "spb_near"),
        (59.9, 30.31, 59.9, 30.31, "same_point"),
        (0.0, 0.0, 0.0, 1.0, "equator_one_degree_lon"),
        (-33.86, 151.21, 48.86, 2.35, "sydney_paris"),
        (55.75, 37.62, 59.93, 30.33, "moscow_spb"),
    ]
    payload = {
        "description": "Haversine km; must match GeneticRouteOptimizer._haversine_distance and Kotlin Haversine.distanceKm",
        "cases": [
            {
                "id": label,
                "lat1": a,
                "lon1": b,
                "lat2": c,
                "lon2": d,
                "distance_km": haversine_km(a, b, c, d),
            }
            for (a, b, c, d, label) in cases
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
