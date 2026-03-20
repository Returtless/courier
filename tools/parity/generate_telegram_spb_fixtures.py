#!/usr/bin/env python3
"""
Build parity JSON fixtures from Telegram bot sample (SPb, Mar 2026).

Coordinates are taken from Yandex/2GIS links in the bot message (destination of each leg).
Matrix: full directed graph, haversine km + travel_min at constant SPEED_KMH (same for Python/Kotlin).

Outputs under repo parity_fixtures/:
- telegram_spb_route_head5 — first 5 stops of the bot route (fits exhaustive perm in MatrixParityOptimizer)
- telegram_spb_all19 — all 19 orders (for future GA; too large for permutation search)
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "parity_fixtures"

# Depot from first leg (rtext start point)
DEPOT: Tuple[float, float] = (59.946241, 30.560771)

# order_number -> (lat, lon) from bot route links
COORDS: Dict[str, Tuple[float, float]] = {
    "3383220": (59.981667, 30.347446),
    "3387038": (59.980745, 30.332545),
    "3383416": (59.966719, 30.344455),
    "3384112": (59.967229, 30.352261),
    "3383657": (59.981276, 30.322264),
    "3383573": (59.984863, 30.31959),
    "3385032": (59.985747, 30.321936),
    "3383669": (59.974108, 30.314826),
    "3384524": (59.974387, 30.319515),
    "3383457": (59.982272, 30.31522),
    "3383434": (59.993987, 30.323555),
    "3385155": (59.993009, 30.310079),
    "3384382": (59.97468, 30.302636),
    "3384955": (59.968394, 30.304981),
    "3385473": (59.974387, 30.319515),
    "3383456": (59.988143, 30.291547),
    "3384961": (59.987132, 30.309912),
    "3383650": (59.99026, 30.328049),
    "3383894": (59.978255, 30.335182),
}

WINDOWS: Dict[str, Tuple[str, str]] = {
    "3383220": ("10:00", "13:00"),
    "3387038": ("10:00", "14:00"),
    "3383416": ("10:00", "13:00"),
    "3384112": ("10:00", "13:00"),
    "3383657": ("10:00", "13:00"),
    "3383573": ("10:00", "13:00"),
    "3385032": ("10:00", "13:00"),
    "3383669": ("10:00", "13:00"),
    "3384524": ("10:00", "13:00"),
    "3383457": ("10:00", "13:00"),
    "3383434": ("10:00", "13:00"),
    "3385155": ("10:00", "13:00"),
    "3384382": ("10:00", "13:00"),
    "3384955": ("11:00", "14:00"),
    "3385473": ("10:00", "14:00"),
    "3383456": ("11:00", "14:00"),
    "3384961": ("13:30", "18:00"),
    "3383650": ("13:00", "16:00"),
    "3383894": ("12:00", "15:00"),
}

# First five stops as in the Telegram optimized route (exhaustive search still cheap: 5! = 120)
HEAD5 = ["3383434", "3385155", "3385032", "3383669", "3384955"]

# Start: first customer ETA 10:00, bot leg 23 min -> departure ~ 09:37 (Europe/Moscow +03)
START_TIME_ISO = "2026-03-14T09:37:00+03:00"

SPEED_KMH = 40.0  # constant for synthetic matrix; same Python/Kotlin


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(
        dlon / 2
    ) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def r5(x: float) -> float:
    return round(float(x), 5)


def build_matrix(nodes: List[Tuple[float, float]]) -> Dict[str, Dict[str, float]]:
    n = len(nodes)
    m: Dict[str, Dict[str, float]] = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                m[f"{i},{j}"] = {"distance_km": 0.0, "travel_min": 0.0}
                continue
            la, lo = nodes[i]
            lb, lo2 = nodes[j]
            d = haversine_km(la, lo, lb, lo2)
            t = (d / SPEED_KMH) * 60.0
            m[f"{i},{j}"] = {"distance_km": r5(d), "travel_min": r5(t)}
    return m


def payload_for_subset(order_nums: List[str]) -> dict:
    nodes = [DEPOT] + [COORDS[num] for num in order_nums]
    orders = []
    for num in order_nums:
        lat, lon = COORDS[num]
        ws, we = WINDOWS[num]
        orders.append(
            {
                "order_number": num,
                "address": f"SPb order {num}",
                "lat": lat,
                "lon": lon,
                "window_start": ws,
                "window_end": we,
            }
        )
    return {
        "rng_seed": 42,
        "start_location": {"lat": DEPOT[0], "lon": DEPOT[1]},
        "start_time_iso": START_TIME_ISO,
        "settings": {"service_time_minutes": 10},
        "nodes": [{"lat": la, "lon": lo} for la, lo in nodes],
        "route_matrix": build_matrix(nodes),
        "orders": orders,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    head = OUT / "telegram_spb_route_head5"
    head.mkdir(parents=True, exist_ok=True)
    (head / "input.json").write_text(
        json.dumps(payload_for_subset(HEAD5), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (head / "README.md").write_text(
        "Subset of Telegram CourierPlanningBot route (first 5 stops). "
        "Matrix = haversine + constant speed; order/times differ from live 2GIS/Yandex.\n"
        "Regenerate: `python tools/parity/generate_telegram_spb_fixtures.py` "
        "then `python tools/export_optimizer_golden.py --fixture parity_fixtures/telegram_spb_route_head5`.\n",
        encoding="utf-8",
    )

    all19 = sorted(COORDS.keys(), key=lambda x: int(x))
    big = OUT / "telegram_spb_all19"
    big.mkdir(parents=True, exist_ok=True)
    (big / "input.json").write_text(
        json.dumps(payload_for_subset(all19), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (big / "README.md").write_text(
        "All 19 orders from the same Telegram sample. "
        "Too many permutations for MatrixParityOptimizer; use after Kotlin GA port. "
        "Regenerate input with `python tools/parity/generate_telegram_spb_fixtures.py`.\n",
        encoding="utf-8",
    )

    print("Wrote", head / "input.json")
    print("Wrote", big / "input.json")


if __name__ == "__main__":
    main()
