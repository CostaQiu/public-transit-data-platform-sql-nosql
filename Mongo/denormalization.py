import os
from urllib.parse import quote_plus

import pandas as pd
import pymongo
from pymongo import UpdateOne
from sqlalchemy import create_engine
from dotenv import load_dotenv

# --- 1) Load configuration from environment (.env overrides defaults) ---
load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "Window76##")
MYSQL_DB = os.getenv("MYSQL_DB", "transit")
MYSQL_ECHO = os.getenv("MYSQL_ECHO", "false").lower() == "true"

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongouser:secretpassword@localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "transit")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "stop_timetables")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "100000"))  

# --- 2) Create database connections ---
mysql_connection_string = (
    f"mysql+pymysql://{MYSQL_USER}:{quote_plus(MYSQL_PASSWORD)}@"
    f"{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
)
mysql_engine = create_engine(mysql_connection_string, echo=MYSQL_ECHO, pool_pre_ping=True)

try:
    mongo_client = pymongo.MongoClient(MONGO_URI)
except Exception as e:
    raise SystemExit(f"Failed to connect to MongoDB with URI '{MONGO_URI}'. Set MONGO_URI in .env. Error: {e}")
mongo_db = mongo_client[MONGO_DB]
mongo_collection = mongo_db[MONGO_COLLECTION]

# Ensure geospatial index for location queries
try:
    mongo_collection.create_index([("location", "2dsphere")])
except pymongo.errors.OperationFailure as e:
    if getattr(e, 'code', None) == 13:
        raise SystemExit("MongoDB authentication required. Please set a valid MONGO_URI in .env, for example: 'mongodb://username:password@localhost:27017/?authSource=admin'")
    raise

# --- 3) Extract-Transform-Load in chunks ---
offset = 0

base_sql = """
SELECT
    st.stop_id, s.stop_name, s.stop_code, s.stop_lat, s.stop_lon,
    r.route_id, r.route_short_name, r.route_long_name,
    t.trip_id, t.service_id, t.trip_headsign, st.departure_time
FROM stop_times st 
JOIN stops s ON s.stop_id = st.stop_id
JOIN trips t ON t.trip_id = st.trip_id
JOIN routes r ON r.route_id = t.route_id
ORDER BY st.stop_id, st.departure_time 
LIMIT %s OFFSET %s
"""

print("Starting ETL: reading from MySQL and writing denormalized documents to MongoDB...")
print(f"MySQL -> {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}")
print(f"MongoDB -> {MONGO_URI}, db={MONGO_DB}, collection={MONGO_COLLECTION}")
print("Clearing existing MongoDB documents...")
mongo_collection.delete_many({})

while True:
    print(f"Extracting rows {offset} to {offset + CHUNK_SIZE}...")
    query = base_sql % (CHUNK_SIZE, offset)
    try:
        chunk_df = pd.read_sql_query(query, mysql_engine)
    except Exception as e:
        print(f"Error during SQL query: {e}")
        break

    if chunk_df.empty:
        print("No more rows. ETL complete.")
        break

    # Group by stop and build batched upserts into MongoDB
    bulk_ops = []
    for stop_id, group in chunk_df.groupby('stop_id'):
        stop_info = group.iloc[0]

        upcoming_services = []
        for _, row in group.iterrows():
            upcoming_services.append({
                "route_id": row['route_id'],
                "route_short_name": row['route_short_name'],
                "route_long_name": row['route_long_name'],
                "trip_id": row['trip_id'],
                "service_id": row['service_id'],
                "trip_headsign": row['trip_headsign'],
                "departure_time": str(row['departure_time'])
            })

        # Prepare stop_code as string when available
        stop_code_value = None
        try:
            val = stop_info['stop_code']
            if pd.notna(val):
                stop_code_value = str(val)
        except Exception:
            stop_code_value = None

        bulk_ops.append(
            UpdateOne(
                {"_id": str(stop_id)},
                {
                    "$setOnInsert": {
                        "_id": str(stop_id),
                        "stop_id": str(stop_id),
                        "stop_name": stop_info['stop_name'],
                        "stop_code": stop_code_value,
                        "location": {
                            "type": "Point",
                            "coordinates": [stop_info['stop_lon'], stop_info['stop_lat']]
                        }
                    },
                    "$push": {"upcoming_services": {"$each": upcoming_services}}
                },
                upsert=True
            )
        )

    if bulk_ops:
        try:
            mongo_collection.bulk_write(bulk_ops, ordered=False)
            print(f"Wrote {len(bulk_ops)} stop documents (upsert/push).")
        except Exception as e:
            print(f"Error during MongoDB bulk_write: {e}")
            break

    offset += CHUNK_SIZE

print("MongoDB load complete!")