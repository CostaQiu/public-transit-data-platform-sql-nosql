## GTA Public Transit Analytics & Timetables — Codebase README

This repository implements a full pipeline on a large GTFS dataset for the GTA:
- Normalize and index the feed in MySQL for analytics (Q1–Q4)
- Export CSVs for fast, reproducible demos
- Denormalize into MongoDB for low‑latency stop timetables
- Serve a lightweight UI (Leaflet + Chart.js) via Flask

For the poster/report assets, see the `reporting/` folder (Markdown report and A1 poster).

---

## Directory Structure

```
Public Transit/
├─ dataset/                      # Raw GTFS text files (agency.txt, trips.txt, stop_times.txt, ...)
├─ SQL/
│  ├─ app.py                     # Flask API for analytics (Q1–Q4); CSV fast path fallback
│  ├─ sql_utils.py               # SQLAlchemy engine + optimized queries + view creation (Q4)
│  ├─ csv_backend.py             # Pandas readers for precomputed CSVs
│  ├─ templates/index.html       # Bootstrap tabs for Q1–Q4
│  ├─ static/app.js              # Leaflet maps, Chart.js charts, table rendering
│  ├─ data/                      # Precomputed CSVs (q1_*.csv, q2_*.csv, q3_*.csv, q4_*.csv)
│  ├─ Q1_busiest_stop.sql        # Reference SQL for Q1
│  ├─ Q2 average duration.sql    # Reference SQL for Q2 (CTE)
│  ├─ Q3 transfer points.sql     # Reference SQL for Q3 (CTE)
│  ├─ Q4 service frequency.sql   # Reference SQL + view for Q4
│  ├─ index and view.sql         # Index DDLs + view helper
│  ├─ transit schema.sql         # Base schema (tables, keys) for MySQL
│  └─ generate_csv.py            # (Optional) batch job to regenerate CSVs
├─ Mongo/
│  ├─ denormalization.py         # MySQL→Mongo ETL, batched; builds stop‑centric documents
│  ├─ app.py                     # Flask API for timetables (get_stops, get_routes_for_stop, get_arrivals)
│  └─ index.html                 # Simple UI for timetable exploration (if used)
├─ reporting/                    # Poster/report deliverables
│  ├─ report.md                  # Project report in Markdown
│  └─ poster_A1.*                # A1 poster (PDF/PNG)
├─ requirements.txt              # Python dependencies
├─ env.example                   # Example .env with connection settings
└─ README.md                     # This file
```

---

## Tech Stack

- **Python 3.10+**
- **Flask** (APIs/UI hosting)
- **SQLAlchemy**, **PyMySQL** (MySQL access)
- **Pandas** (CSV generation/reading)
- **PyMongo** (MongoDB access)
- **Leaflet** (maps), **Chart.js** (charts), **Bootstrap** (layout) via CDN
- **MySQL 8+**, **MongoDB 5+**

---

## Quick Start

1) Clone and create a virtual environment

```
python -m venv .venv
. .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Configure environment

Create `.env` at the repo root (copy from `env.example`) and set:

```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=...        # your password
MYSQL_DB=transit

MONGO_URI=mongodb://mongouser:secretpassword@localhost:27017/?authSource=admin
MONGO_DB=transit
MONGO_COLLECTION=stop_timetables

MYSQL_ECHO=false
CHUNK_SIZE=100000
```

3) Prepare MySQL schema and load data

- Ensure a database named `transit` exists.
- From your MySQL client, run the base schema script:

```
SOURCE SQL/transit schema.sql;
```

- Import GTFS tables from `dataset/*.txt` (use MySQL import wizard, `LOAD DATA INFILE`, or your ETL of choice).
- Apply indexes and helper view (recommended):

```
SOURCE SQL/index and view.sql;
```

4) Validate analytics queries (SQL path)

- Optional: regenerate CSVs for Q1–Q4 (ensures fast demos and consistent numbers):

```
python SQL/generate_csv.py
```

- Start the Flask analytics app (SQL):

```
python -m SQL.app
# serves at http://127.0.0.1:5050
```

Open the UI and try each tab (Q1–Q4). If CSVs are present in `SQL/data/`, the API will use them; otherwise it will execute the optimized SQL.

5) Build MongoDB timetables (NoSQL path)

- Ensure MongoDB is running and the credentials in `.env` are valid.
- If using Docker for MongoDB, **start Docker Desktop first** and make sure a container is up. Example one‑liner:

```
docker run -d --name transit-mongo -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=mongouser \
  -e MONGO_INITDB_ROOT_PASSWORD=secretpassword \
  mongo:6
```

- With the container above, the default `MONGO_URI` works:

```
MONGO_URI=mongodb://mongouser:secretpassword@localhost:27017/?authSource=admin
```

- Run the denormalization ETL:

```
python Mongo/denormalization.py
```

Notes:
- Runs in **batches** (`CHUNK_SIZE`, default 100k). Full load of the GTA feed typically takes **20+ minutes**.
- Creates a 2dsphere index on `location` in `transit.stop_timetables`.

6) Start the Mongo timetable API

```
python Mongo/app.py
# serves at http://127.0.0.1:5000
```

Important: when running MongoDB in Docker, **Docker Desktop must remain running** while executing `Mongo/denormalization.py` and `Mongo/app.py`.

Available endpoints:
- `GET /get_stops` → list of stops (`stop_id`, `stop_name`, `stop_code`)
- `GET /get_routes_for_stop?stop_id=...&service_id=1|2|3` → unique `(route_short_name, trip_headsign)` pairs (excludes NOT IN SERVICE)
- `GET /get_arrivals?stop_id=...&route_short_name=..&trip_headsign=..&service_id=1|2|3` → sorted times (public service only)

---

## Reproducing the Full Workflow

1) **Acquire data**: place GTFS files in `dataset/` (already present in this repo snapshot).
2) **Load to MySQL**: create tables from `SQL/transit schema.sql` and import all `dataset/*.txt`.
3) **Optimize**: apply `SQL/index and view.sql` to create indexes and the hourly frequency view.
4) **Run analytics**:
   - Option A (fast path): generate CSVs with `SQL/generate_csv.py` and serve via Flask (`python -m SQL.app`).
   - Option B (live SQL): start Flask directly (`python -m SQL.app`) and let it execute SQL; the app will auto‑ensure the Q4 view.
5) **Denormalize to MongoDB**: execute `Mongo/denormalization.py` to build `stop_timetables` documents.
6) **Timetable API**: start `Mongo/app.py` and use the endpoints to fetch grouped, public timetables per stop.

---

## Performance Notes (what to check if slow)

- Ensure the following MySQL indexes exist:
  - `trips(route_id)`, `trips(service_id)`
  - `stop_times(trip_id)`, `stop_times(stop_id)`
  - `stop_times(trip_id, departure_time)` (for Q2 duration min/max)
- Verify the view `vw_hourly_frequency` exists (the SQL app will create it if missing).
- Push `service_id` filters early and keep `LIMIT` values modest for interactive use.
- Use the CSV fast path for demos; regenerate CSVs after schema/data refreshes.

---

## Troubleshooting

- "Access denied" connecting to MongoDB → check `MONGO_URI` and that `authSource=admin` matches your user.
- MySQL connection refused → confirm host/port and that the user has `FILE`/`LOAD DATA` permissions if importing via SQL.
- Empty UI tables → ensure CSVs exist in `SQL/data/` or that the database is populated and reachable.

---

## License & Acknowledgments

- GTFS data © respective transit agencies. Used for academic purposes.
- This project is an academic deliverable for CP/DA 603.


