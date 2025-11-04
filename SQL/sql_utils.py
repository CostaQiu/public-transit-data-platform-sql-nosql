import os
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Result


def get_mysql_connection_url() -> str:
    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "Window76##")
    db = os.getenv("MYSQL_DB", "transit")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"


def get_engine() -> Engine:
    echo = os.getenv("MYSQL_ECHO", "false").lower() == "true"
    url = get_mysql_connection_url()
    return create_engine(url, echo=echo, pool_pre_ping=True, pool_recycle=300)


def _sanitize_limit(limit_param: Optional[str]) -> Optional[int]:
    if not limit_param:
        return 20
    value = str(limit_param).strip().lower()
    if value == "all":
        return None
    try:
        n = int(value)
        if n <= 0:
            return 20
        return n
    except ValueError:
        if value in {"10", "20", "50"}:
            return int(value)
        return 20


def _service_id_filter(service_id_param: Optional[str]) -> Optional[str]:
    if service_id_param in {None, "", "4", 4}:
        return None
    return str(service_id_param)


def ensure_hourly_frequency_view(engine: Engine) -> None:
    with engine.begin() as conn:
        exists_sql = text(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.VIEWS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vw_hourly_frequency'
            """
        )
        cnt = conn.execute(exists_sql).scalar_one()
        if int(cnt) == 0:
            create_view_sql = text(
                """
                CREATE VIEW vw_hourly_frequency AS
                SELECT
                    t.route_id,
                    t.service_id,
                    HOUR(st.departure_time) AS hour_of_day,
                    COUNT(DISTINCT t.trip_id) AS trips_per_hour
                FROM stop_times st
                JOIN trips t ON t.trip_id = st.trip_id
                GROUP BY t.route_id, t.service_id, hour_of_day
                """
            )
            conn.execute(create_view_sql)


def query_q1_busiest_stops(engine: Engine, service_id: Optional[str], limit_param: Optional[str]) -> List[Dict[str, Any]]:
    service_filter = _service_id_filter(service_id)
    limit_value = _sanitize_limit(limit_param)

    base_sql = (
        "SELECT st.stop_id, s.stop_code, s.stop_name, s.stop_lat, s.stop_lon, "
        "COUNT(*) AS total_trip_events, COUNT(DISTINCT t.route_id) AS num_unique_routes "
        "FROM stop_times st "
        "JOIN trips t ON t.trip_id = st.trip_id "
        "JOIN stops s ON s.stop_id = st.stop_id "
    )
    where_clause = "WHERE (:service_id IS NULL OR t.service_id = :service_id) "
    group_order = "GROUP BY st.stop_id, s.stop_code, s.stop_name, s.stop_lat, s.stop_lon ORDER BY total_trip_events DESC "
    limit_clause = f"LIMIT {limit_value}" if limit_value is not None else ""

    sql = text(base_sql + where_clause + group_order + limit_clause)
    params = {"service_id": service_filter}

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    result: List[Dict[str, Any]] = []
    for r in rows:
        result.append({
            "stop_id": r["stop_id"],
            "stop_code": r.get("stop_code"),
            "stop_name": r["stop_name"],
            "stop_lat": float(f"{r['stop_lat']:.6f}"),
            "stop_lon": float(f"{r['stop_lon']:.6f}"),
            "total_trip_events": int(r["total_trip_events"]),
            "num_unique_routes": int(r["num_unique_routes"]),
        })
    return result


def query_q3_transfer_points(engine: Engine, service_id: Optional[str], limit_param: Optional[str]) -> List[Dict[str, Any]]:
    service_filter = _service_id_filter(service_id)
    limit_value = _sanitize_limit(limit_param)

    with_clause = (
        "WITH UniqueStopRoutes AS (\n"
        "    SELECT DISTINCT st.stop_id, t.route_id\n"
        "    FROM stop_times st\n"
        "    JOIN trips t ON t.trip_id = st.trip_id\n"
        "    WHERE (:service_id IS NULL OR t.service_id = :service_id)\n"
        ")\n"
    )
    main_sql = (
        "SELECT s.stop_id, s.stop_code, s.stop_name, s.stop_lat, s.stop_lon, COUNT(USR.route_id) AS num_unique_routes\n"
        "FROM stops s\n"
        "JOIN UniqueStopRoutes USR ON USR.stop_id = s.stop_id\n"
        "GROUP BY s.stop_id, s.stop_code, s.stop_name, s.stop_lat, s.stop_lon\n"
        "HAVING num_unique_routes >= 2\n"
        "ORDER BY num_unique_routes DESC\n"
    )
    limit_clause = f"LIMIT {limit_value}" if limit_value is not None else ""
    sql = text(with_clause + main_sql + limit_clause)
    params = {"service_id": service_filter}

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    result: List[Dict[str, Any]] = []
    for r in rows:
        result.append({
            "stop_id": r["stop_id"],
            "stop_code": r.get("stop_code"),
            "stop_name": r["stop_name"],
            "stop_lat": float(f"{r['stop_lat']:.6f}"),
            "stop_lon": float(f"{r['stop_lon']:.6f}"),
            "num_unique_routes": int(r["num_unique_routes"]),
        })
    return result


def _q2_trip_stats_cte() -> str:
    return (
        "WITH trip_stats AS (\n"
        "    SELECT\n"
        "        t.route_id,\n"
        "        t.service_id,\n"
        "        TIMESTAMPDIFF(SECOND, MIN(st.departure_time), MAX(st.arrival_time)) AS trip_duration_seconds,\n"
        "        (MAX(st.shape_dist_traveled) - MIN(st.shape_dist_traveled)) AS trip_distance\n"
        "    FROM stop_times st\n"
        "    JOIN trips t ON t.trip_id = st.trip_id\n"
        "    GROUP BY t.trip_id, t.route_id, t.service_id\n"
        "    HAVING trip_duration_seconds > 60\n"
        ")\n"
    )


def query_q2_avg_duration_speed(
    engine: Engine, service_id: Optional[str], limit_param: Optional[str]
) -> Dict[str, Any]:
    limit_value = _sanitize_limit(limit_param)
    service_filter = _service_id_filter(service_id)

    cte = _q2_trip_stats_cte()

    def _round2(val: Optional[float]) -> Optional[float]:
        if val is None:
            return None
        return float(f"{val:.2f}")

    with engine.begin() as conn:
        if service_filter is None:
            # Global per route for ranking
            global_sql = text(
                cte
                + (
                    "SELECT r.route_long_name AS route, r.route_short_name AS route_short,\n"
                    "       COUNT(*) AS total_trips,\n"
                    "       AVG(ts.trip_distance) AS avg_trip_distance_km,\n"
                    "       AVG(ts.trip_duration_seconds)/60.0 AS avg_duration_min,\n"
                    "       AVG(ts.trip_distance / NULLIF(ts.trip_duration_seconds,0) * 3600) AS avg_speed_kmh\n"
                    "FROM trip_stats ts\n"
                    "JOIN routes r ON r.route_id = ts.route_id\n"
                    "GROUP BY r.route_long_name\n"
                    "ORDER BY avg_duration_min DESC\n"
                )
                + (f"LIMIT {limit_value}" if limit_value is not None else "")
            )
            global_rows = conn.execute(global_sql).mappings().all()
            selected_routes = {r["route"] for r in global_rows}

            # Per service per route
            per_service_sql = text(
                cte
                + (
                    "SELECT r.route_long_name AS route, r.route_short_name AS route_short, ts.service_id,\n"
                    "       COUNT(*) AS total_trips,\n"
                    "       AVG(ts.trip_distance) AS avg_trip_distance_km,\n"
                    "       AVG(ts.trip_duration_seconds)/60.0 AS avg_duration_min,\n"
                    "       STDDEV(ts.trip_duration_seconds)/60.0 AS duration_stddev_min,\n"
                    "       AVG(ts.trip_distance / NULLIF(ts.trip_duration_seconds,0) * 3600) AS avg_speed_kmh\n"
                    "FROM trip_stats ts\n"
                    "JOIN routes r ON r.route_id = ts.route_id\n"
                    "GROUP BY r.route_long_name, ts.service_id\n"
                )
            )
            ps_rows = conn.execute(per_service_sql).mappings().all()

            # Build response
            route_to_services: Dict[str, Dict[str, Any]] = {}
            for r in global_rows:
                route_to_services[r["route"]] = {
                    "route_long_name": r["route"],
                    "route_short_name": r.get("route_short"),
                    "global": {
                        "total_trips": int(r["total_trips"]),
                        "avg_trip_distance_km": _round2(r["avg_trip_distance_km"]),
                        "avg_duration_min": _round2(r["avg_duration_min"]),
                        "avg_speed_kmh": _round2(r["avg_speed_kmh"]),
                    },
                    "services": [],
                }

            for r in ps_rows:
                route = r["route"]
                if route not in selected_routes:
                    continue
                route_to_services[route]["services"].append(
                    {
                        "service_id": str(r["service_id"]),
                        "total_trips": int(r["total_trips"]),
                        "avg_trip_distance_km": _round2(r["avg_trip_distance_km"]),
                        "avg_duration_min": _round2(r["avg_duration_min"]),
                        "duration_stddev_min": _round2(r["duration_stddev_min"]),
                        "avg_speed_kmh": _round2(r["avg_speed_kmh"]),
                    }
                )

            # Overall weighted averages across selected routes (using global total_trips)
            total_trips_all = sum(v["global"]["total_trips"] for v in route_to_services.values()) or 1
            overall_duration = sum(
                (v["global"]["avg_duration_min"] or 0.0) * v["global"]["total_trips"]
                for v in route_to_services.values()
            ) / total_trips_all
            overall_speed = sum(
                (v["global"]["avg_speed_kmh"] or 0.0) * v["global"]["total_trips"]
                for v in route_to_services.values()
            ) / total_trips_all

            return {
                "mode": "whole_week",
                "routes": list(route_to_services.values()),
                "overall": {
                    "avg_duration_min": _round2(overall_duration),
                    "avg_speed_kmh": _round2(overall_speed),
                },
            }
        else:
            # Single service filter
            sql = text(
                cte
                + (
                    "SELECT r.route_long_name AS route, r.route_short_name AS route_short, ts.service_id, COUNT(*) AS total_trips,\n"
                    "       AVG(ts.trip_distance) AS avg_trip_distance_km,\n"
                    "       AVG(ts.trip_duration_seconds)/60.0 AS avg_duration_min,\n"
                    "       STDDEV(ts.trip_duration_seconds)/60.0 AS duration_stddev_min,\n"
                    "       AVG(ts.trip_distance / NULLIF(ts.trip_duration_seconds,0) * 3600) AS avg_speed_kmh\n"
                    "FROM trip_stats ts\n"
                    "JOIN routes r ON r.route_id = ts.route_id\n"
                    "WHERE ts.service_id = :service_id\n"
                    "GROUP BY r.route_long_name, ts.service_id\n"
                    "ORDER BY avg_duration_min DESC\n"
                )
                + (f"LIMIT {limit_value}" if limit_value is not None else "")
            )
            rows = conn.execute(sql, {"service_id": service_filter}).mappings().all()

            total_trips_all = sum(int(r["total_trips"]) for r in rows) or 1
            overall_duration = sum(
                float(r["avg_duration_min"]) * int(r["total_trips"]) for r in rows
            ) / total_trips_all
            overall_speed = sum(
                float(r["avg_speed_kmh"]) * int(r["total_trips"]) for r in rows
            ) / total_trips_all

            return {
                "mode": "single_service",
                "routes": [{
                    "route_long_name": r["route"],
                    "route_short_name": r.get("route_short"),
                    "service_id": str(r["service_id"]),
                    "total_trips": int(r["total_trips"]),
                    "avg_trip_distance_km": _round2(r["avg_trip_distance_km"]),
                    "avg_duration_min": _round2(r["avg_duration_min"]),
                    "duration_stddev_min": _round2(r["duration_stddev_min"]),
                    "avg_speed_kmh": _round2(r["avg_speed_kmh"]),
                } for r in rows],
                "overall": {
                    "avg_duration_min": _round2(overall_duration),
                    "avg_speed_kmh": _round2(overall_speed),
                },
            }


def query_q4_hourly_frequency(
    engine: Engine, service_id: Optional[str], limit_param: Optional[str]
) -> Dict[str, Any]:
    ensure_hourly_frequency_view(engine)
    service_filter = _service_id_filter(service_id)
    limit_value = _sanitize_limit(limit_param)

    with engine.begin() as conn:
        # Determine top routes by total_daily_trips (sum of trips_per_hour)
        rank_sql = text(
            (
                "SELECT r.route_long_name AS route, "+
                ("vhf.service_id AS service_id, " if service_filter is not None else "")+
                "SUM(vhf.trips_per_hour) AS total_daily_trips\n"
                "FROM vw_hourly_frequency vhf\n"
                "JOIN routes r ON r.route_id = vhf.route_id\n"
            )
            + ("WHERE vhf.service_id = :service_id\n" if service_filter is not None else "")
            + (
                "GROUP BY r.route_long_name"
                + (", vhf.service_id\n" if service_filter is not None else "\n")
                + "ORDER BY total_daily_trips DESC\n"
            )
            + (f"LIMIT {limit_value}" if limit_value is not None else "")
        )
        rank_rows = conn.execute(
            rank_sql, ({"service_id": service_filter} if service_filter is not None else {})
        ).mappings().all()
        selected_routes = {r["route"] for r in rank_rows}

        data_sql = text(
            (
                "SELECT r.route_long_name AS route, r.route_short_name AS route_short, vhf.service_id, vhf.hour_of_day, vhf.trips_per_hour\n"
                "FROM vw_hourly_frequency vhf\n"
                "JOIN routes r ON r.route_id = vhf.route_id\n"
            )
            + ("WHERE vhf.service_id = :service_id\n" if service_filter is not None else "")
            + "ORDER BY r.route_long_name, vhf.service_id, vhf.hour_of_day\n"
        )
        rows = conn.execute(
            data_sql, ({"service_id": service_filter} if service_filter is not None else {})
        ).mappings().all()

    # Group by route and optionally by service
    from collections import defaultdict

    route_to_hours: Dict[str, Dict[str, Dict[int, int]]] = defaultdict(lambda: defaultdict(dict))
    route_short_by_route: Dict[str, Optional[str]] = {}
    max_hour = 0
    for r in rows:
        route = r["route"]
        route_short = r.get("route_short")
        sid = str(r["service_id"])
        hour = int(r["hour_of_day"]) if r["hour_of_day"] is not None else 0
        trips = int(r["trips_per_hour"]) if r["trips_per_hour"] is not None else 0
        max_hour = max(max_hour, hour)
        route_to_hours[route][sid][hour] = trips
        if route not in route_short_by_route:
            route_short_by_route[route] = route_short

    # Keep only selected routes
    route_to_hours = {k: v for k, v in route_to_hours.items() if k in selected_routes}

    # Build response
    result_routes: List[Dict[str, Any]] = []
    for route, service_map in route_to_hours.items():
        if service_filter is None:
            # Sum across services
            hourly_counts: Dict[int, int] = defaultdict(int)
            for sid_map in service_map.values():
                for h, c in sid_map.items():
                    hourly_counts[h] += c
            hours_sorted = sorted(hourly_counts.keys())
            series = [{"hour": h, "trips": hourly_counts.get(h, 0)} for h in hours_sorted]
            total = sum(hourly_counts.values())
            # Per-service totals 1/2/3 and average
            per_sid_totals: Dict[str, int] = {}
            for sid_key in ["1", "2", "3"]:
                sid_map = service_map.get(sid_key, {})
                per_sid_totals[sid_key] = sum(sid_map.values()) if sid_map else 0
            avg_daily = sum(per_sid_totals.values()) / 3.0
            result_routes.append(
                {
                    "route_long_name": route,
                    "route_short_name": route_short_by_route.get(route),
                    "service_id": "all",
                    "hourly": series,
                    "total_daily_trips": total,
                    "totals_by_service": per_sid_totals,
                    "average_daily_trips": avg_daily,
                }
            )
        else:
            sid = service_filter
            sid_map = service_map.get(sid, {})
            hours_sorted = sorted(sid_map.keys())
            series = [{"hour": h, "trips": sid_map.get(h, 0)} for h in hours_sorted]
            total = sum(sid_map.values())
            result_routes.append(
                {
                    "route_long_name": route,
                    "route_short_name": route_short_by_route.get(route),
                    "service_id": sid,
                    "hourly": series,
                    "total_daily_trips": total,
                }
            )

    return {
        "max_hour": max_hour,
        "routes": result_routes,
    }


