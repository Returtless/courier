#!/usr/bin/env python3
"""
Generate expected.json for parity fixtures using GeneticRouteOptimizer + ParityMapsService.

Usage (from repo root):
  python tools/export_optimizer_golden.py --fixture parity_fixtures/tiny_two_orders

Requires PYTHONPATH=. or run from repo root:
  python tools/export_optimizer_golden.py --fixture parity_fixtures/tiny_two_orders
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from src.models.route_types import Order  # noqa: E402
from src.services.genetic_rng import SplitMix64Rng, patch_random_module  # noqa: E402
from src.services.route_optimizer_genetic import GeneticRouteOptimizer  # noqa: E402
from parity.fixture_maps_service import ParityMapsService  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("export_golden")


def _parse_time_hhmm(s: Any) -> Optional[time]:
    if s is None:
        return None
    if isinstance(s, time):
        return s
    if isinstance(s, str) and s.strip():
        parts = s.strip().split(":")
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        return time(h, m)
    return None


def _orders_from_payload(orders_in: List[dict]) -> List[Order]:
    out: List[Order] = []
    for o in orders_in:
        if not isinstance(o, dict):
            continue
        ws = o.get("window_start")
        we = o.get("window_end")
        manual_iso = o.get("manual_arrival_iso")
        manual_dt = None
        if isinstance(manual_iso, str) and manual_iso.strip():
            dt = datetime.fromisoformat(manual_iso.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            manual_dt = dt
        out.append(
            Order(
                order_number=(str(o.get("order_number")).strip() if o.get("order_number") else None),
                address=(str(o.get("address") or "").strip() or ""),
                latitude=o.get("lat"),
                longitude=o.get("lon"),
                phone=o.get("phone"),
                customer_name=o.get("customer_name"),
                delivery_time_start=_parse_time_hhmm(ws),
                delivery_time_end=_parse_time_hhmm(we),
                manual_arrival_time=manual_dt,
                comment=o.get("comment"),
            )
        )
    return out


def _iso_trunc_seconds(dt: datetime) -> str:
    """Match Kotlin MatrixParityOptimizer ZonedDateTime.toPythonIso() (truncate to whole seconds)."""
    return dt.replace(microsecond=0).isoformat()


def _optimized_to_expected(
    optimized: Any,
    start_time_naive: datetime,
    tzinfo: Any,
    order_date: Any,
) -> Dict[str, Any]:
    def _with_tz(dt: datetime) -> datetime:
        return dt.replace(tzinfo=tzinfo) if tzinfo is not None else dt

    route_points: List[Dict[str, Any]] = []
    for p in optimized.points:
        eta_dt = p.estimated_arrival
        eta_dt_tz = _with_tz(eta_dt)
        window_end_dt = (
            datetime.combine(order_date, p.order.delivery_time_end)
            if p.order.delivery_time_end is not None
            else None
        )
        is_late = bool(window_end_dt is not None and eta_dt > window_end_dt)
        point: Dict[str, Any] = {
            "order_number": p.order.order_number or "",
            "estimated_arrival_iso": _iso_trunc_seconds(eta_dt_tz),
            "distance_from_previous_km": float(p.distance_from_previous),
            "time_from_previous_min": float(p.time_from_previous),
            "is_late": is_late,
        }
        if p.order.delivery_time_start is not None:
            point["window_start"] = p.order.delivery_time_start.strftime("%H:%M")
        if p.order.delivery_time_end is not None:
            point["window_end"] = p.order.delivery_time_end.strftime("%H:%M")
        route_points.append(point)

    est_iso = _iso_trunc_seconds(_with_tz(optimized.estimated_completion))
    return {
        "route_points": route_points,
        "total_distance_km": float(optimized.total_distance),
        "total_time_min": float(optimized.total_time),
        "estimated_completion_iso": est_iso,
    }


def run_fixture(fixture_dir: Path, dump_intermediate: bool = False) -> None:
    fixture_dir = fixture_dir.resolve()
    input_path = fixture_dir / "input.json"
    raw = json.loads(input_path.read_text(encoding="utf-8"))

    rng_seed = int(raw.get("rng_seed", 42))
    patch_random_module(SplitMix64Rng(rng_seed))
    logger.info("rng_seed=%s (SplitMix64, same as Kotlin)", rng_seed)

    start_loc = raw["start_location"]
    start_lat, start_lon = float(start_loc["lat"]), float(start_loc["lon"])
    start_time_iso = raw.get("start_time_iso") or "2026-01-29T09:20:00+03:00"
    start_dt = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
    tzinfo = start_dt.tzinfo
    start_time_naive = start_dt.replace(tzinfo=None)

    nodes = raw["nodes"]
    matrix = raw["route_matrix"]
    maps = ParityMapsService(nodes, matrix)

    orders = _orders_from_payload(raw.get("orders", []) or [])
    service_min = raw.get("settings", {}).get("service_time_minutes", 10)
    try:
        service_min = int(service_min)
    except Exception:
        service_min = 10

    opt = GeneticRouteOptimizer(maps)
    optimized = opt.optimize_route_sync(
        orders=orders,
        start_location=(start_lat, start_lon),
        start_time=start_time_naive,
        user_id=None,
        service_time_minutes_override=service_min,
    )

    expected = _optimized_to_expected(
        optimized, start_time_naive, tzinfo, start_time_naive.date()
    )
    expected["meta"] = {"rng_seed": rng_seed, "fixture": fixture_dir.name}

    out_path = fixture_dir / "expected.json"
    out_path.write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote %s", out_path)

    if dump_intermediate:
        inter = fixture_dir / "intermediate"
        inter.mkdir(exist_ok=True)
        # Placeholder for future cluster dumps
        (inter / "placeholder.txt").write_text("use --dump-intermediate in later phases\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", required=True, help="Path to fixture directory containing input.json")
    ap.add_argument("--dump-intermediate", action="store_true")
    args = ap.parse_args()
    run_fixture(Path(args.fixture), dump_intermediate=args.dump_intermediate)


if __name__ == "__main__":
    main()
