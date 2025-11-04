import os
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request
import numpy as np  # for JSON-safe conversion

# Support running as a module (python -m SQL.app) and as a script (python SQL/app.py)
try:
    from .sql_utils import (
        ensure_hourly_frequency_view,
        get_engine,
        query_q1_busiest_stops as sql_q1,
        query_q2_avg_duration_speed as sql_q2,
        query_q3_transfer_points as sql_q3,
        query_q4_hourly_frequency as sql_q4,
    )
    from . import csv_backend
except Exception:  # pragma: no cover
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from SQL.sql_utils import (
        ensure_hourly_frequency_view,
        get_engine,
        query_q1_busiest_stops as sql_q1,
        query_q2_avg_duration_speed as sql_q2,
        query_q3_transfer_points as sql_q3,
        query_q4_hourly_frequency as sql_q4,
    )
    from SQL import csv_backend


app = Flask(__name__, template_folder="templates", static_folder="static")

# --- Helpers (must be defined before routes) ---
def _to_json_safe(obj):
    """Recursively convert numpy/pandas scalars to native Python types for JSON."""
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    # numpy types
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    # pandas NA-like
    try:
        if obj is None:
            return None
        if isinstance(obj, float) and np.isnan(obj):
            return None
    except Exception:
        pass
    return obj

# CSV directory
data_dir = os.path.join(os.path.dirname(__file__), 'data')

def _has_csv(filename: str) -> bool:
    try:
        return os.path.exists(os.path.join(data_dir, filename))
    except Exception:
        return False

# Eagerly prepare SQL engine only if needed (lazy init below)
engine = None
def _ensure_engine():
    global engine
    if engine is None:
        engine = get_engine()
        ensure_hourly_frequency_view(engine)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/q1")
def api_q1():
    service_id = request.args.get("service_id")
    limit_param = request.args.get("limit")
    if _has_csv('q1_busiest_stops.csv'):
        data = csv_backend.query_q1_busiest_stops(service_id, limit_param)
    else:
        _ensure_engine()
        data = sql_q1(engine, service_id, limit_param)
    return jsonify(_to_json_safe({"items": data}))


@app.get("/api/q2")
def api_q2():
    service_id = request.args.get("service_id")
    limit_param = request.args.get("limit")
    if _has_csv('q2_avg_duration_speed.csv'):
        data = csv_backend.query_q2_avg_duration_speed(service_id, limit_param)
    else:
        _ensure_engine()
        data = sql_q2(engine, service_id, limit_param)
    return jsonify(_to_json_safe(data))


@app.get("/api/q3")
def api_q3():
    service_id = request.args.get("service_id")
    limit_param = request.args.get("limit")
    if _has_csv('q3_transfer_points.csv'):
        data = csv_backend.query_q3_transfer_points(service_id, limit_param)
    else:
        _ensure_engine()
        data = sql_q3(engine, service_id, limit_param)
    return jsonify(_to_json_safe({"items": data}))


@app.get("/api/q4")
def api_q4():
    service_id = request.args.get("service_id")
    limit_param = request.args.get("limit")
    if _has_csv('q4_hourly_frequency.csv'):
        data = csv_backend.query_q4_hourly_frequency(service_id, limit_param)
    else:
        _ensure_engine()
        data = sql_q4(engine, service_id, limit_param)
    return jsonify(_to_json_safe(data))


if __name__ == "__main__":
    # Run on a different port to avoid conflict with Mongo UI
    app.run(host="127.0.0.1", port=5050, debug=True)


