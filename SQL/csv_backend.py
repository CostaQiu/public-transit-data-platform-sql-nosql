import os
from typing import Any, Dict, List, Optional

import pandas as pd


DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

_q1_df: Optional[pd.DataFrame] = None
_q2_df: Optional[pd.DataFrame] = None
_q3_df: Optional[pd.DataFrame] = None
_q4_df: Optional[pd.DataFrame] = None


def _load() -> None:
    global _q1_df, _q2_df, _q3_df, _q4_df
    if _q1_df is None:
        _q1_df = pd.read_csv(os.path.join(DATA_DIR, 'q1_busiest_stops.csv'))
    if _q2_df is None:
        _q2_df = pd.read_csv(os.path.join(DATA_DIR, 'q2_avg_duration_speed.csv'))
    if _q3_df is None:
        _q3_df = pd.read_csv(os.path.join(DATA_DIR, 'q3_transfer_points.csv'))
    if _q4_df is None:
        _q4_df = pd.read_csv(os.path.join(DATA_DIR, 'q4_hourly_frequency.csv'))


def _sanitize_limit(limit_param: Optional[str]) -> Optional[int]:
    if not limit_param:
        return 20
    v = str(limit_param).strip().lower()
    if v == 'all':
        return None
    try:
        n = int(v)
        return n if n > 0 else 20
    except ValueError:
        return 20


def query_q1_busiest_stops(service_id: Optional[str], limit_param: Optional[str]) -> List[Dict[str, Any]]:
    _load()
    sid = '4' if service_id in (None, '', '4', 4) else str(service_id)
    df = _q1_df[_q1_df['service_id'].astype(str) == sid].copy()
    df.sort_values('total_trip_events', ascending=False, inplace=True)
    limit_value = _sanitize_limit(limit_param)
    if limit_value is not None:
        df = df.head(limit_value)
    return [
        {
            'stop_id': r.stop_id,
            'stop_code': r.stop_code if pd.notna(r.stop_code) else None,
            'stop_name': r.stop_name,
            'stop_lat': float(r.stop_lat),
            'stop_lon': float(r.stop_lon),
            'total_trip_events': int(r.total_trip_events),
            'num_unique_routes': int(r.num_unique_routes),
        }
        for _, r in df.iterrows()
    ]


def query_q3_transfer_points(service_id: Optional[str], limit_param: Optional[str]) -> List[Dict[str, Any]]:
    _load()
    sid = '4' if service_id in (None, '', '4', 4) else str(service_id)
    df = _q3_df[_q3_df['service_id'].astype(str) == sid].copy()
    df.sort_values('num_unique_routes', ascending=False, inplace=True)
    limit_value = _sanitize_limit(limit_param)
    if limit_value is not None:
        df = df.head(limit_value)
    return [
        {
            'stop_id': r.stop_id,
            'stop_code': r.stop_code if pd.notna(r.stop_code) else None,
            'stop_name': r.stop_name,
            'stop_lat': float(r.stop_lat),
            'stop_lon': float(r.stop_lon),
            'num_unique_routes': int(r.num_unique_routes),
        }
        for _, r in df.iterrows()
    ]


def query_q2_avg_duration_speed(service_id: Optional[str], limit_param: Optional[str]) -> Dict[str, Any]:
    _load()
    sid = '4' if service_id in (None, '', '4', 4) else str(service_id)
    df = _q2_df.copy()
    limit_value = _sanitize_limit(limit_param)

    def _round2(x: Optional[float]) -> Optional[float]:
        if x is None or (isinstance(x, float) and (pd.isna(x))):
            return None
        return float(f"{float(x):.2f}")

    if sid == '4':
        # select top routes by avg_duration_min (global rows in CSV)
        gdf = df[df['service_id'].astype(str) == '4'].copy()
        gdf.sort_values('avg_duration_min', ascending=False, inplace=True)
        if limit_value is not None:
            gdf = gdf.head(limit_value)
        selected = set(zip(gdf['route_long_name'], gdf['route_short_name']))
        # per-service stats for selected routes
        ps = df[df['service_id'].astype(str).isin(['1', '2', '3'])]
        ps = ps[ps.apply(lambda r: (r['route_long_name'], r['route_short_name']) in selected, axis=1)]
        routes = []
        for (rl, rs), g in gdf.groupby(['route_long_name', 'route_short_name']):
            services = []
            for sid2 in ['1', '2', '3']:
                r = ps[(ps['route_long_name'] == rl) & (ps['route_short_name'] == rs) & (ps['service_id'].astype(str) == sid2)]
                if len(r):
                    row = r.iloc[0]
                    services.append({
                        'service_id': sid2,
                        'total_trips': int(row['total_trips']),
                        'avg_trip_distance_km': _round2(row['avg_trip_distance_km']),
                        'avg_duration_min': _round2(row['avg_duration_min']),
                        'duration_stddev_min': _round2(row['duration_stddev_min']) if pd.notna(row['duration_stddev_min']) else None,
                        'avg_speed_kmh': _round2(row['avg_speed_kmh']),
                    })
            routes.append({
                'route_long_name': rl,
                'route_short_name': rs if pd.notna(rs) else None,
                'global': {
                    'total_trips': int(g.iloc[0]['total_trips']),
                    'avg_trip_distance_km': _round2(g.iloc[0]['avg_trip_distance_km']),
                    'avg_duration_min': _round2(g.iloc[0]['avg_duration_min']),
                    'avg_speed_kmh': _round2(g.iloc[0]['avg_speed_kmh']),
                },
                'services': services,
            })
        # overall
        total_trips_all = sum(r['global']['total_trips'] for r in routes) or 1
        overall_duration = sum((r['global']['avg_duration_min'] or 0) * r['global']['total_trips'] for r in routes) / total_trips_all
        overall_speed = sum((r['global']['avg_speed_kmh'] or 0) * r['global']['total_trips'] for r in routes) / total_trips_all
        return {
            'mode': 'whole_week',
            'routes': routes,
            'overall': {
                'avg_duration_min': _round2(overall_duration),
                'avg_speed_kmh': _round2(overall_speed),
            }
        }
    else:
        sdf = df[df['service_id'].astype(str) == sid].copy()
        sdf.sort_values('avg_duration_min', ascending=False, inplace=True)
        if limit_value is not None:
            sdf = sdf.head(limit_value)
        total_trips_all = int(sdf['total_trips'].sum()) or 1
        overall_duration = float((sdf['avg_duration_min'] * sdf['total_trips']).sum()) / total_trips_all
        overall_speed = float((sdf['avg_speed_kmh'] * sdf['total_trips']).sum()) / total_trips_all
        routes = []
        for _, r in sdf.iterrows():
            routes.append({
                'route_long_name': r['route_long_name'],
                'route_short_name': r['route_short_name'] if pd.notna(r['route_short_name']) else None,
                'service_id': sid,
                'total_trips': int(r['total_trips']),
                'avg_trip_distance_km': _round2(r['avg_trip_distance_km']),
                'avg_duration_min': _round2(r['avg_duration_min']),
                'duration_stddev_min': _round2(r['duration_stddev_min']) if pd.notna(r['duration_stddev_min']) else None,
                'avg_speed_kmh': _round2(r['avg_speed_kmh']),
            })
        return {
            'mode': 'single_service',
            'routes': routes,
            'overall': {
                'avg_duration_min': _round2(overall_duration),
                'avg_speed_kmh': _round2(overall_speed),
            },
        }


def query_q4_hourly_frequency(service_id: Optional[str], limit_param: Optional[str]) -> Dict[str, Any]:
    _load()
    sid = '4' if service_id in (None, '', '4', 4) else str(service_id)
    df = _q4_df[_q4_df['service_id'].astype(str) == sid].copy()
    # Determine top routes by total_daily_trips
    totals = df.groupby(['route_long_name', 'route_short_name'], as_index=False)['trips_per_hour'].sum()
    totals.rename(columns={'trips_per_hour': 'total_daily_trips'}, inplace=True)
    totals.sort_values('total_daily_trips', ascending=False, inplace=True)
    limit_value = _sanitize_limit(limit_param)
    if limit_value is not None:
        totals = totals.head(limit_value)
    selected = set(zip(totals['route_long_name'], totals['route_short_name']))
    out_routes: List[Dict[str, Any]] = []
    for (rl, rs), g in df.groupby(['route_long_name', 'route_short_name']):
        if (rl, rs) not in selected:
            continue
        hours = g.sort_values('hour_of_day')
        route_obj = {
            'route_long_name': rl,
            'route_short_name': rs if pd.notna(rs) else None,
            'service_id': sid,
            'hourly': [{'hour': int(h), 'trips': int(v)} for h, v in zip(hours['hour_of_day'], hours['trips_per_hour'])],
            'total_daily_trips': int(totals[(totals['route_long_name'] == rl) & (totals['route_short_name'] == rs)]['total_daily_trips'].iloc[0]),
        }
        # For whole-week mode return per-service totals and average
        if sid == '4':
            per_service = (
                _q4_df[_q4_df['service_id'].astype(str).isin(['1','2','3'])]
                .groupby(['route_long_name', 'route_short_name', 'service_id'], as_index=False)['trips_per_hour']
                .sum()
            )
            rows = per_service[(per_service['route_long_name'] == rl) & (per_service['route_short_name'] == rs)]
            totals_by_service = {'1': 0, '2': 0, '3': 0}
            for _, r in rows.iterrows():
                totals_by_service[str(r['service_id'])] = int(r['trips_per_hour'])
            route_obj['totals_by_service'] = totals_by_service
            route_obj['average_daily_trips'] = sum(totals_by_service.values()) / 3.0
        out_routes.append(route_obj)
    max_hour = int(df['hour_of_day'].max()) if len(df) else 0
    return {
        'max_hour': max_hour,
        'routes': out_routes,
    }


