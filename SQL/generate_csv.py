import os
from typing import List

import pandas as pd
from sqlalchemy import text

from .sql_utils import get_engine, ensure_hourly_frequency_view, _q2_trip_stats_cte


DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def generate_q1(engine) -> None:
    # service 1/2/3 and all (4)
    frames: List[pd.DataFrame] = []
    with engine.begin() as conn:
        base = (
            "SELECT st.stop_id, s.stop_code, s.stop_name, s.stop_lat, s.stop_lon, "
            "COUNT(*) AS total_trip_events, COUNT(DISTINCT t.route_id) AS num_unique_routes, :sid AS service_id\n"
            "FROM stop_times st JOIN trips t ON t.trip_id = st.trip_id JOIN stops s ON s.stop_id = st.stop_id\n"
            "{where}\n"
            "GROUP BY st.stop_id, s.stop_code, s.stop_name, s.stop_lat, s.stop_lon\n"
        )
        for sid in ['1', '2', '3']:
            sql = text(base.format(where="WHERE t.service_id = :sid"))
            df = pd.read_sql(sql, conn, params={"sid": sid})
            frames.append(df)
        # Whole week (4) computed without service filter
        sql_all = text(base.format(where=""))
        df_all = pd.read_sql(sql_all, conn, params={"sid": '4'})
        frames.append(df_all)
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(os.path.join(DATA_DIR, 'q1_busiest_stops.csv'), index=False)


def generate_q3(engine) -> None:
    # service 1/2/3 and all (4)
    frames: List[pd.DataFrame] = []
    with engine.begin() as conn:
        # UniqueStopRoutes CTE with optional service filter
        for sid in ['1', '2', '3']:
            sql = text(
                "WITH UniqueStopRoutes AS (\n"
                "  SELECT DISTINCT st.stop_id, t.route_id\n"
                "  FROM stop_times st JOIN trips t ON t.trip_id = st.trip_id\n"
                "  WHERE t.service_id = :sid\n"
                ")\n"
                "SELECT s.stop_id, s.stop_code, s.stop_name, s.stop_lat, s.stop_lon, COUNT(USR.route_id) AS num_unique_routes, :sid AS service_id\n"
                "FROM stops s JOIN UniqueStopRoutes USR ON USR.stop_id = s.stop_id\n"
                "GROUP BY s.stop_id, s.stop_code, s.stop_name, s.stop_lat, s.stop_lon\n"
                "HAVING num_unique_routes >= 2\n"
                "ORDER BY num_unique_routes DESC\n"
            )
            df = pd.read_sql(sql, conn, params={"sid": sid})
            frames.append(df)
        # Whole week (4) uses all trips
        sql_all = text(
            "WITH UniqueStopRoutes AS (\n"
            "  SELECT DISTINCT st.stop_id, t.route_id\n"
            "  FROM stop_times st JOIN trips t ON t.trip_id = st.trip_id\n"
            ")\n"
            "SELECT s.stop_id, s.stop_code, s.stop_name, s.stop_lat, s.stop_lon, COUNT(USR.route_id) AS num_unique_routes, '4' AS service_id\n"
            "FROM stops s JOIN UniqueStopRoutes USR ON USR.stop_id = s.stop_id\n"
            "GROUP BY s.stop_id, s.stop_code, s.stop_name, s.stop_lat, s.stop_lon\n"
            "HAVING num_unique_routes >= 2\n"
            "ORDER BY num_unique_routes DESC\n"
        )
        df_all = pd.read_sql(sql_all, conn)
        frames.append(df_all)
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(os.path.join(DATA_DIR, 'q3_transfer_points.csv'), index=False)


def generate_q2(engine) -> None:
    # per route per service and global (4)
    with engine.begin() as conn:
        cte = _q2_trip_stats_cte()
        sql = text(
            cte
            + (
                "SELECT r.route_long_name, r.route_short_name, ts.service_id,\n"
                "       COUNT(*) AS total_trips,\n"
                "       AVG(ts.trip_distance) AS avg_trip_distance_km,\n"
                "       AVG(ts.trip_duration_seconds)/60.0 AS avg_duration_min,\n"
                "       STDDEV(ts.trip_duration_seconds)/60.0 AS duration_stddev_min,\n"
                "       AVG(ts.trip_distance / NULLIF(ts.trip_duration_seconds,0) * 3600) AS avg_speed_kmh\n"
                "FROM trip_stats ts JOIN routes r ON r.route_id = ts.route_id\n"
                "GROUP BY r.route_long_name, r.route_short_name, ts.service_id\n"
            )
        )
        df = pd.read_sql(sql, conn)
        # Global (4) weighted by total_trips across services
        grouped = df.groupby(["route_long_name", "route_short_name"], as_index=False).apply(
            lambda g: pd.Series({
                "service_id": '4',
                "total_trips": g["total_trips"].sum(),
                "avg_trip_distance_km": (g["avg_trip_distance_km"] * g["total_trips"]).sum() / max(g["total_trips"].sum(), 1),
                "avg_duration_min": (g["avg_duration_min"] * g["total_trips"]).sum() / max(g["total_trips"].sum(), 1),
                "duration_stddev_min": None,
                "avg_speed_kmh": (g["avg_speed_kmh"] * g["total_trips"]).sum() / max(g["total_trips"].sum(), 1),
            })
        ).reset_index(drop=True)
        out = pd.concat([df, grouped], ignore_index=True)
        out.to_csv(os.path.join(DATA_DIR, 'q2_avg_duration_speed.csv'), index=False)


def generate_q4(engine) -> None:
    ensure_hourly_frequency_view(engine)
    with engine.begin() as conn:
        sql = text(
            "SELECT r.route_long_name, r.route_short_name, vhf.service_id, vhf.hour_of_day, vhf.trips_per_hour\n"
            "FROM vw_hourly_frequency vhf JOIN routes r ON r.route_id = vhf.route_id\n"
        )
        df = pd.read_sql(sql, conn)
        # Create '4' rows summing across service_ids
        summed = (
            df.groupby(["route_long_name", "route_short_name", "hour_of_day"], as_index=False)["trips_per_hour"].sum()
        )
        summed["service_id"] = '4'
        out = pd.concat([df, summed], ignore_index=True)
        out.to_csv(os.path.join(DATA_DIR, 'q4_hourly_frequency.csv'), index=False)


def main() -> None:
    _ensure_data_dir()
    engine = get_engine()
    generate_q1(engine)
    generate_q2(engine)
    generate_q3(engine)
    generate_q4(engine)
    print(f"CSV files written to {DATA_DIR}")


if __name__ == '__main__':
    main()


