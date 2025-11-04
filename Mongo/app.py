# Import necessary libraries
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS # Used to allow browser access
import os
from dotenv import load_dotenv
import pymongo
from collections import defaultdict

# --- 1. Initialize Flask App and MongoDB Connection ---
app = Flask(__name__)
CORS(app) # Allow Cross-Origin Requests (so the HTML file can access Python)

# Load environment variables (.env overrides defaults)
load_dotenv()

try:
    # Hard-coded MongoDB connection (Docker default user/pass, admin auth)
    # Change these if your container uses different credentials
    MONGO_URI = "mongodb://mongouser:secretpassword@localhost:27017/?authSource=admin"
    MONGO_DB = "transit"
    MONGO_COLLECTION = "stop_timetables"

    client = pymongo.MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[MONGO_COLLECTION]
    
    # Check if the 'stop_name' index exists, create it if not
    try:
        existing_indexes = collection.index_information()
        if "stop_name_1" not in existing_indexes:
            collection.create_index("stop_name")
            print("Created index on 'stop_name'.")
    except pymongo.errors.OperationFailure as e:
        # Handle authentication errors with a helpful message
        if getattr(e, 'code', None) == 13:
            raise SystemExit(
                "MongoDB authentication required. Set MONGO_URI in .env, e.g.: "
                "'mongodb://username:password@localhost:27017/?authSource=admin'"
            )
        raise

except pymongo.errors.ConnectionFailure as e:
    print(f"Could not connect to MongoDB: {e}")
    exit()

# --- 2. API Endpoint: Get All Stops List ---
@app.route('/get_stops', methods=['GET'])
def get_stops():
    """
    This endpoint queries MongoDB for all unique stop names and IDs
    to populate the frontend dropdown menu.
    """
    try:
        # Query all documents, but only return 'stop_id' and 'stop_name' fields
        # .sort("stop_name", 1) ensures the dropdown list is alphabetical
        stops = list(collection.find(
            {}, 
            {"stop_id": 1, "stop_name": 1, "stop_code": 1, "_id": 0}
        ).sort("stop_name", 1))
        
        return jsonify(stops)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 3. API Endpoint: Get Timetable for a Specific Stop ---
@app.route('/get_timetable', methods=['GET'])
def get_timetable():
    """
    This endpoint retrieves the full document for a given 'stop_id'
    and groups the timetable by route and direction.
    """
    # Get stop_id from the URL parameters (e.g., /get_timetable?stop_id=1000)
    stop_id_query = request.args.get('stop_id')
    
    if not stop_id_query:
        return jsonify({"error": "Missing 'stop_id' parameter"}), 400

    # --- 3A. Query MongoDB ---
    stop_data = collection.find_one({"stop_id": stop_id_query})

    if not stop_data:
        return jsonify({"error": f"Stop ID not found: {stop_id_query}"}), 404

    # --- 3B. Transform Data (Group in Python) ---
    # defaultdict is a special dictionary that auto-creates nested dictionaries
    # Structure: { "Route Name": { "Direction (Headsign)": [List of Times] } }
    routes_schedule = defaultdict(lambda: defaultdict(list))
    
    upcoming_services = stop_data.get("upcoming_services", [])

    for service in upcoming_services:
        route_name = service.get("route_long_name", "Unknown Route")
        headsign = service.get("trip_headsign", "Unknown Direction")
        
        # Format the time string (remove 'X days ')
        time_str = str(service.get("departure_time", "N/A"))
        if "days" in time_str:
            simple_time = time_str.split(" ")[-1]
        else:
            simple_time = time_str
            
        routes_schedule[route_name][headsign].append(simple_time)
    
    # --- 3C. Sort the time lists ---
    sorted_schedule = {}
    for route, directions in routes_schedule.items():
        sorted_schedule[route] = {}
        for headsign, times in directions.items():
            # Sort by time string
            sorted_schedule[route][headsign] = sorted(times)
            
    # Return the grouped and sorted data as JSON to the frontend
    return jsonify(sorted_schedule)

# --- 3D. API Endpoint: Get route_short_name + trip_headsign combos for a stop ---
@app.route('/get_routes_for_stop', methods=['GET'])
def get_routes_for_stop():
    """
    Returns unique pairs of (route_short_name, trip_headsign) that pass through the given stop.
    Excludes entries where trip_headsign == "NOT IN SERVICE".
    """
    stop_id_query = request.args.get('stop_id')
    service_id_filter = request.args.get('service_id')  # optional, limit to 1/2/3
    if not stop_id_query:
        return jsonify({"error": "Missing 'stop_id' parameter"}), 400

    stop_data = collection.find_one({"stop_id": stop_id_query}, {"upcoming_services": 1, "_id": 0})
    if not stop_data:
        return jsonify([])

    allowed_services = {"1", "2", "3"}
    unique_pairs = set()
    for service in stop_data.get("upcoming_services", []):
        sid = str(service.get("service_id")) if service.get("service_id") is not None else None
        if sid not in allowed_services:
            continue
        if service_id_filter is not None and sid != str(service_id_filter):
            continue
        headsign = service.get("trip_headsign")
        if headsign is None or headsign == "NOT IN SERVICE":
            continue
        route_short_name = service.get("route_short_name")
        if route_short_name is None:
            continue
        unique_pairs.add((str(route_short_name), str(headsign)))

    # Return as list of dicts sorted by route_short_name then headsign
    pairs_list = sorted([{"route_short_name": r, "trip_headsign": h} for r, h in unique_pairs], key=lambda x: (x["route_short_name"], x["trip_headsign"]))
    return jsonify(pairs_list)


# --- 3E. API Endpoint: Get arrival times (sorted) with optional route/headsign filter ---
@app.route('/get_arrivals', methods=['GET'])
def get_arrivals():
    """
    Returns arrival times (departure_time in source) for a stop, optionally filtered by
    route_short_name and trip_headsign. Times are returned as strings sorted ascending.

    Query params:
      - stop_id (required)
      - route_short_name (optional)
      - trip_headsign (optional)
    """
    stop_id_query = request.args.get('stop_id')
    route_short_name = request.args.get('route_short_name')
    trip_headsign = request.args.get('trip_headsign')
    service_id_filter = request.args.get('service_id')  # optional

    if not stop_id_query:
        return jsonify({"error": "Missing 'stop_id' parameter"}), 400

    stop_data = collection.find_one({"stop_id": stop_id_query}, {"upcoming_services": 1, "_id": 0})
    if not stop_data:
        return jsonify({"times": [], "count": 0})

    def simplify_time(time_value):
        # Convert times like "1 days 03:00:00" to "03:00:00"
        s = str(time_value)
        if "days" in s:
            return s.split(" ")[-1]
        return s

    allowed_services = {"1", "2", "3"}

    # If a specific route+headsign is requested -> flat list
    if route_short_name is not None and trip_headsign is not None:
        times = []
        for service in stop_data.get("upcoming_services", []):
            sid = str(service.get("service_id")) if service.get("service_id") is not None else None
            if sid not in allowed_services:
                continue
            if service_id_filter is not None and sid != str(service_id_filter):
                continue
            if service.get("trip_headsign") != trip_headsign:
                continue
            if str(service.get("route_short_name")) != route_short_name:
                continue
            times.append(simplify_time(service.get("departure_time", "")))

        times = sorted([t for t in times if t])
        return jsonify({
            "times": times,
            "count": len(times)
        })

    # Otherwise: group by route_id + headsign
    groups_map = {}
    for service in stop_data.get("upcoming_services", []):
        sid = str(service.get("service_id")) if service.get("service_id") is not None else None
        if sid not in allowed_services:
            continue
        if service_id_filter is not None and sid != str(service_id_filter):
            continue

        headsign = service.get("trip_headsign")
        if headsign is None or headsign == "NOT IN SERVICE":
            continue

        route_id = str(service.get("route_id")) if service.get("route_id") is not None else ""
        key = (route_id, headsign)
        if key not in groups_map:
            groups_map[key] = {
                "route_id": route_id,
                "route_short_name": str(service.get("route_short_name")) if service.get("route_short_name") is not None else "",
                "trip_headsign": headsign,
                "times": []
            }
        groups_map[key]["times"].append(simplify_time(service.get("departure_time", "")))

    groups = []
    total_count = 0
    for group in groups_map.values():
        # sort each group's times and compute count
        group_times = sorted([t for t in group["times"] if t])
        group["times"] = group_times
        group["count"] = len(group_times)
        total_count += group["count"]
    # sort groups by route_short_name then headsign
    groups = sorted(groups_map.values(), key=lambda g: (g["route_short_name"], g["trip_headsign"]))

    return jsonify({
        "groups": groups,
        "total_count": total_count
    })

# --- 4. Root Route: Serve the HTML page ---
@app.route('/')
def index():
    """
    When a user visits the root URL (http://127.0.0.1:5000),
    send the 'index.html' file.
    """
    # Ensure 'index.html' is in the same directory as 'app.py'
    return send_from_directory('.', 'index.html')

# --- Start the Server ---
if __name__ == '__main__':
    print("Server starting... Please open http://127.0.0.1:5000 in your browser")
    app.run(debug=True) # debug=True allows auto-reload on code changes