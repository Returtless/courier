#!/usr/bin/env python3
"""
Write intermediate/cluster_orders.json: result of GeneticRouteOptimizer._cluster_and_synchronize_orders
for a parity fixture (same input as export_optimizer_golden).

Usage (repo root):
  python tools/parity/export_cluster_intermediate.py --fixture parity_fixtures/tiny_two_orders

For stable ordering vs Kotlin, run with TZ=Europe/Moscow (or same as JVM test default).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from export_optimizer_golden import _orders_from_payload  # noqa: E402
from src.services.route_optimizer_genetic import GeneticRouteOptimizer  # noqa: E402
from parity.fixture_maps_service import ParityMapsService  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("export_cluster")


def _serialize_order(o) -> dict:
    ws = o.delivery_time_start.strftime("%H:%M") if o.delivery_time_start else None
    we = o.delivery_time_end.strftime("%H:%M") if o.delivery_time_end else None
    return {
        "order_number": o.order_number or "",
        "window_start": ws,
        "window_end": we,
        "lat": o.latitude,
        "lon": o.longitude,
    }


def run_fixture(fixture_dir: Path) -> None:
    fixture_dir = fixture_dir.resolve()
    raw = json.loads((fixture_dir / "input.json").read_text(encoding="utf-8"))
    start_loc = raw["start_location"]
    start_lat, start_lon = float(start_loc["lat"]), float(start_loc["lon"])
    start_time_iso = raw.get("start_time_iso") or "2026-01-29T09:20:00+03:00"
    start_dt = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
    start_time_naive = start_dt.replace(tzinfo=None)

    nodes = raw["nodes"]
    matrix = raw["route_matrix"]
    maps = ParityMapsService(nodes, matrix)
    orders = _orders_from_payload(raw.get("orders", []) or [])
    orders_with_coords = [o for o in orders if o.latitude and o.longitude]

    opt = GeneticRouteOptimizer(maps)
    synced = opt._cluster_and_synchronize_orders(
        orders_with_coords,
        start_time_naive,
        (start_lat, start_lon),
    )

    out_dir = fixture_dir / "intermediate"
    out_dir.mkdir(exist_ok=True)
    payload = {
        "description": "After _cluster_and_synchronize_orders (genetic.py)",
        "start_time_iso": start_time_iso,
        "orders_out": [_serialize_order(o) for o in synced],
    }
    path = out_dir / "cluster_orders.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote %s", path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", required=True)
    args = ap.parse_args()
    run_fixture(Path(args.fixture))


if __name__ == "__main__":
    main()
