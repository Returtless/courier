import json
from datetime import datetime


def ping() -> str:
    return "courierpy ok"


def optimize_route_json(payload_json: str) -> str:
    """
    JSON bridge entrypoint.

    Input schema (minimal):
    {
      "start_location": {"lat": 59.9, "lon": 30.3},
      "start_time_iso": "2026-01-29T09:20:00+03:00",
      "settings": {"service_time_minutes": 7},
      "orders": [
        {"order_number":"3319990","address":"...","lat":..,"lon":..,"window_start":"10:00","window_end":"13:00", "phone": "...", "customer_name": "...", "manual_arrival_iso": null}
      ],
      "route_matrix": { "key(from,to)": {"distance_km": 1.2, "travel_min": 4.0} }
    }

    Output schema:
    { "route_points":[...], "total_distance_km":..., "total_time_min":..., "estimated_completion_iso":"..." }

    Note:
    For MVP we return a stub which preserves schema. Next step is to wire the existing
    GA optimizer logic with a matrix-based MapsService adapter.
    """
    payload = json.loads(payload_json)
    start_time = payload.get("start_time_iso")
    orders = payload.get("orders", [])

    # Stub: keep input order. TODO: wire real GA optimizer using matrix-based routing adapter.
    route_points = []
    total_distance_km = 0.0
    total_time_min = 0.0

    try:
        current_time = _parse_dt(start_time) if start_time else datetime.now()
    except (TypeError, ValueError):
        current_time = datetime.now()
    service_time = payload.get("settings", {}).get("service_time_minutes", 10)

    for idx, o in enumerate(orders):
        eta_iso = current_time.isoformat()
        route_points.append(
            {
                "position": idx + 1,
                "order_number": o.get("order_number"),
                "estimated_arrival_iso": eta_iso,
                "call_time_iso": eta_iso,
                "distance_from_previous_km": 0.0,
                "time_from_previous_min": 0.0,
                "window_start": o.get("window_start"),
                "window_end": o.get("window_end"),
                "is_late": False,
            }
        )
        if current_time:
            # no travel time in stub, only service time
            current_time = current_time + _minutes(service_time)

    out = {
        "route_points": route_points,
        "total_distance_km": total_distance_km,
        "total_time_min": total_time_min,
        "estimated_completion_iso": current_time.isoformat(),
    }
    return json.dumps(out, ensure_ascii=False)


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _minutes(m: int):
    from datetime import timedelta

    return timedelta(minutes=float(m))

