import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast


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

    This function is executed inside Chaquopy on Android, so it must be defensive:
    - Use Android-provided API keys from the payload (via env vars) before importing `src.*` settings.
    - Ensure datetime parsing/output is compatible with Kotlin `Instant.parse()` (include timezone if provided).
    """
    payload = json.loads(payload_json)

    def _as_nonempty_str(v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return str(v)

    def _parse_iso_dt_remove_tz(s: Optional[str]) -> Tuple[datetime, Optional[Any]]:
        """
        Parse ISO-8601 datetime and return:
        - naive datetime for Python optimization internals (avoid tz-aware vs tz-naive arithmetic)
        - original tzinfo (so we can add it back for Kotlin Instant.parse compatibility)
        """
        if not s:
            dt = datetime.now()
            return dt, None
        dt = datetime.fromisoformat(cast(str, s))
        tzinfo = dt.tzinfo
        if tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt, tzinfo

    start_time_naive, tzinfo = _parse_iso_dt_remove_tz(payload.get("start_time_iso"))
    start_location = payload.get("start_location") or {}

    # Service time is needed for correct ETA calculations.
    service_time_minutes = payload.get("settings", {}).get("service_time_minutes", 10)
    try:
        service_time_minutes = int(service_time_minutes)
    except Exception:
        service_time_minutes = 10

    # Pass API keys through env vars *before* importing src.config/settings.
    # Android Gradle will provide these fields to the payload.
    yandex_key = _as_nonempty_str(payload.get("yandex_api_key"))
    two_gis_key = _as_nonempty_str(payload.get("two_gis_api_key"))
    if yandex_key:
        os.environ["YANDEX_MAPS_API_KEY"] = yandex_key
    if two_gis_key:
        os.environ["TWO_GIS_API_KEY"] = two_gis_key

    try:
        from src.models.route_types import Order
        from src.services.maps_service import MapsService
        from src.services.route_optimizer import RouteOptimizer

        orders_in = payload.get("orders", []) or []
        orders: List[Order] = []

        for o in orders_in:
            if not isinstance(o, dict):
                continue
            window_start = o.get("window_start")
            window_end = o.get("window_end")
            if isinstance(window_start, str) and not window_start.strip():
                window_start = None
            if isinstance(window_end, str) and not window_end.strip():
                window_end = None

            manual_arrival_iso = o.get("manual_arrival_iso")
            manual_dt_naive: Optional[datetime] = None
            if isinstance(manual_arrival_iso, str) and manual_arrival_iso.strip():
                manual_dt, _ = _parse_iso_dt_remove_tz(manual_arrival_iso)
                manual_dt_naive = manual_dt

            orders.append(
                Order(
                    order_number=_as_nonempty_str(o.get("order_number")),
                    address=_as_nonempty_str(o.get("address")) or "",
                    latitude=o.get("lat"),
                    longitude=o.get("lon"),
                    phone=_as_nonempty_str(o.get("phone")),
                    customer_name=_as_nonempty_str(o.get("customer_name")),
                    delivery_time_start=window_start,
                    delivery_time_end=window_end,
                    manual_arrival_time=manual_dt_naive,
                    comment=_as_nonempty_str(o.get("comment")),
                )
            )

        start_lat = float(start_location.get("lat", 0.0))
        start_lon = float(start_location.get("lon", 0.0))

        optimizer = RouteOptimizer(MapsService())
        optimized_route = optimizer.optimize_route_sync(
            orders=orders,
            start_location=(start_lat, start_lon),
            start_time=start_time_naive,
            user_id=None,
            service_time_minutes_override=service_time_minutes,
        )

        def _with_tz(dt: datetime) -> datetime:
            # Kotlin Instant.parse requires offset/Z; add original tz back if present.
            return dt.replace(tzinfo=tzinfo) if tzinfo is not None else dt

        route_points: List[Dict[str, Any]] = []
        order_date = start_time_naive.date()
        for p in optimized_route.points:
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
                "estimated_arrival_iso": eta_dt_tz.isoformat(),
                "distance_from_previous_km": float(p.distance_from_previous),
                "time_from_previous_min": float(p.time_from_previous),
                "is_late": is_late,
            }

            if p.order.delivery_time_start is not None:
                point["window_start"] = p.order.delivery_time_start.strftime("%H:%M")
            if p.order.delivery_time_end is not None:
                point["window_end"] = p.order.delivery_time_end.strftime("%H:%M")

            # Intentionally omit `call_time_iso`:
            # Android RouteScreen will compute it as `ETA - callAdvanceMinutes`.

            route_points.append(point)

        estimated_completion_iso = _with_tz(optimized_route.estimated_completion).isoformat()
        out = {
            "route_points": route_points,
            "total_distance_km": float(optimized_route.total_distance),
            "total_time_min": float(optimized_route.total_time),
            "estimated_completion_iso": estimated_completion_iso,
        }
        return json.dumps(out, ensure_ascii=False)

    except Exception as e:
        # Return a schema-compatible response so Android can show a meaningful UI state.
        # Also print error to Logcat via stdout.
        print(f"optimizer_bridge.optimize_route_json error: {e}")
        out = {
            "route_points": [],
            "total_distance_km": 0.0,
            "total_time_min": 0.0,
            "estimated_completion_iso": start_time_naive.replace(tzinfo=tzinfo).isoformat() if tzinfo is not None else start_time_naive.isoformat(),
        }
        return json.dumps(out, ensure_ascii=False)


def _minutes(m: int):
    # Kept for backward compatibility; optimizer_bridge previously used it in the stub.
    from datetime import timedelta
    return timedelta(minutes=float(m))

