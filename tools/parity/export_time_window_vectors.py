#!/usr/bin/env python3
"""Generate parity_fixtures/math_vectors/time_windows.json from src.models.route_types.Order."""
from __future__ import annotations

import json
import sys
from datetime import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.models.route_types import Order  # noqa: E402

OUT = ROOT / "parity_fixtures" / "math_vectors" / "time_windows.json"


def order_to_case(o: Order, case_id: str, note: str = "") -> dict:
    sh = o.delivery_time_start.hour if o.delivery_time_start else None
    sm = o.delivery_time_start.minute if o.delivery_time_start else None
    eh = o.delivery_time_end.hour if o.delivery_time_end else None
    em_ = o.delivery_time_end.minute if o.delivery_time_end else None
    ms, me = o.get_time_window_minutes()
    return {
        "id": case_id,
        "note": note,
        "expect_start_h": sh,
        "expect_start_m": sm,
        "expect_end_h": eh,
        "expect_end_m": em_,
        "expect_min_from_midnight_start": ms,
        "expect_min_from_midnight_end": me,
    }


def main() -> None:
    scenarios = []

    # String window only (triggers _parse_time_window in __init__)
    for cid, w in [
        ("window_spaced", "10:00 - 13:00"),
        ("window_no_space_around_dash", "9:05-12:30"),
        ("window_extra_text", "Доставка с 14:00 - 18:00 сегодня"),
        ("window_single_digit_hours", "8:00 - 9:15"),
    ]:
        o = Order(delivery_time_window=w)
        scenarios.append({**order_to_case(o, cid, w), "delivery_time_window": w})

    # No window -> full day in minutes
    o = Order()
    scenarios.append({**order_to_case(o, "no_fields"), "delivery_time_window": None})

    # Explicit start/end without delivery_time_window string
    o = Order(delivery_time_start=time(11, 45), delivery_time_end=time(16, 0))
    scenarios.append(
        {
            **order_to_case(o, "explicit_times_no_string"),
            "delivery_time_window": None,
            "explicit_start": "11:45",
            "explicit_end": "16:00",
        }
    )

    # Invalid clock in regex match -> ValueError swallowed, times stay None
    o = Order(delivery_time_window="25:00 - 26:00")
    scenarios.append({**order_to_case(o, "invalid_clock_values"), "delivery_time_window": "25:00 - 26:00"})

    # Regex does not match
    o = Order(delivery_time_window="весь день")
    scenarios.append({**order_to_case(o, "no_regex_match"), "delivery_time_window": "весь день"})

    payload = {
        "description": "Time window parity: route_types.Order parsing + get_time_window_minutes",
        "cases": scenarios,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
