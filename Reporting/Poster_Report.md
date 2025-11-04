## GTA Public Transit Data Platform — Poster Report (A1, 24×36 in)

### Title and Team
- **Project**: GTA Public Transit Analytics & Timetable Platform
- **Course**: CP/DA 603 — Database Systems
- **Team**: [Add names]
- **Semester**: [Add term]

### Executive Overview
- **Scope**: Build an end‑to‑end analytics and timetable system on a full GTFS dataset for the Greater Toronto Area (GTA), using MySQL for the relational system of record and MongoDB for a denormalized, stop‑centric timetable store.
- **Scale**:
  - **223 routes**
  - **9,329 stops** (opposite sides of a street are modeled as distinct stops)
  - **131,140 trips** (per day type and per direction are separate trips)
  - **~4.3 million `stop_times` rows**
- **Why full data?** We intentionally processed the entire feed to validate query plans and user experience under realistic load. This ensures that performance claims and insights are meaningful beyond toy examples.
- **Key insights (headline)**:
  - **Busiest hubs** cluster in downtown Toronto and Scarborough, with multiple high‑traffic stops (e.g., near Kennedy Station and along Queen/King corridors).
  - **Transfer corridors** concentrate along **Wilson Avenue** and **Eglinton Avenue**.
  - **504 — KING** delivers the highest number of daily trips (~**1,316** average/day across weekday/Sat/Sun).
  - Weekend service remains robust: vs weekday totals, **Saturday −17.1%**, **Sunday −26.6%**, and **weekend average −21.8%** (by unique trips starting per day).
  - Longest routes exceed **90 km**, but average speeds remain modest (~**18–20 km/h**), reflecting frequent stops and urban traffic.

---

## Dataset Overview

### What the GTFS tables capture
- **`agency`**: feed metadata.
- **`routes`**: published lines; 223 total.
- **`trips`**: directional service instances bound to a specific day type (`service_id`) and route; 131,140 total.
- **`stops`**: stop names and coordinates; 9,329 total.
- **`stop_times`**: per‑trip, per‑stop arrival/departure times; ~4.3M records.
- **`calendar` / `calendar_dates`**: weekday/Saturday/Sunday schedules and exceptions.
- **`shapes`**: geometry points that allow distance estimation and mapping.

### How the tables relate (conceptual)
- **`routes` (1) → `trips` (∞)**: each route has many trips (both directions; each service day type is distinct).
- **`trips` (1) → `stop_times` (∞)**: each trip visits many stops in sequence.
- **`stops` (1) ← `stop_times` (∞)**: each stop is visited by many trips.
- **`calendar` (1) ← `trips` (∞)**: defines which days a trip runs (weekday/Saturday/Sunday).
- **`shapes`**: linked to trips (via `shape_id` in standard GTFS); distance can be approximated using `shape_dist_traveled` in `stop_times`.

### Counting conventions and key numbers
- **Trips are unique by day type and direction**. The same physical pattern contributes separate `trip_id`s for weekday, Saturday, and Sunday, and for each direction.
- Average magnitude: under these conventions, one can estimate roughly **~93 trips/day per route per direction**.
- **All data used**: to rigorously test query plans and application behavior at scale, we used the full dataset, not a sample.

### Why this matters for analysis
- The **size and structure** of the GTFS feed create realistic performance challenges: the heavy table is `stop_times` (~4.3M rows), while aggregation and distinct counting span `trips` and `routes`. The design of queries and indexes must respect this distribution to achieve sub‑6‑second results.

---

## System Architecture (SQL + CSV acceleration + MongoDB)

### High‑level workflow
1. **Relational store (MySQL)**
   - Load GTFS CSVs into normalized tables.
   - Validate/refine primary and foreign keys based on the ER diagram (e.g., `routes.route_id`, `trips.route_id`, `trips.service_id`, `stop_times.trip_id`, `stop_times.stop_id`).
   - Add indexes targeted to analytical needs (see Technical Highlights).
   - Implement the four analytics questions (Q1–Q4) with careful filter ordering, CTEs, and a view.
2. **CSV acceleration path (Pandas)**
   - Export stable results (Q1–Q4) to CSV files to speed iteration and ensure deterministic poster numbers.
   - The API serves CSVs if present; otherwise it executes SQL. JSON shapes remain identical.
3. **Denormalized store (MongoDB)**
   - A separate Python ETL reads MySQL in large batches, groups by `stop_id`, and writes **one document per stop** in MongoDB (collection `stop_timetables`).
   - Documents include the stop’s location and an `upcoming_services` array with route, headsign, service day, and time. A 2dsphere index is created on `location`.
   - Full ETL (all data) runs in **batches** and takes **20+ minutes** on development hardware.

### Components and responsibilities
- **MySQL**: source of truth, integrity, and analytics (joins, group‑bys, ranking).
- **Flask API (SQL path)**: exposes `/api/q1..q4` with optional parameters `service_id` (weekday/weekend/whole week) and `limit`. Ensures the analytical view exists (for Q4) at startup.
- **CSV cache**: if a corresponding CSV exists (e.g., `q4_hourly_frequency.csv`), the endpoint serves Pandas‑backed data immediately; otherwise SQLAlchemy executes the optimized SQL.
- **Flask API (Mongo path)**: endpoints return stop lists, unique `(route_short_name, headsign)` pairs per stop, and sorted timetable times. These filter to **public services only** (service_ids {1,2,3}) and exclude "NOT IN SERVICE" entries.
- **Client application**: maps (Leaflet) and charts (Chart.js) visualize the analytics outputs and present stop timetables; forms switch day types and the number of rows.

### Operational characteristics
- **Sub‑6s responses** for all four analytics queries after indexing and query tuning (CTEs, view, filter ordering). CSVs return faster still, which is ideal for classroom demos and reproducibility.
- **ETL throughput** (Mongo): chunked reads (default 100k rows) keep memory usage stable; bulk upserts group by `stop_id` to minimize round‑trips.

---

## High‑Level System Architecture (Mermaid)

```mermaid
graph LR
  A[GTFS .txt] --> B[MySQL normalized]
  B --> C[Indexing & keys]

  C --> D[SQL analytics (Q1-Q4)]
  D --> E[CSV results]
  E --> F[Flask API]
  F --> G[Browser UI]

  B --> H[Denormalize ETL (batches)]
  H --> I[MongoDB stop_timetables]
  I --> J[Timetable API]
  J --> K[Browser UI]
```

### Notes on the diagram
- **Normalization & Indexing**: raw GTFS text files are loaded into a normalized schema; indexes on `trips(route_id, service_id)` and `stop_times(trip_id, stop_id, trip_id+departure_time)` enable fast joins and aggregations.
- **SQL Analytics**:
  - **Q2/Q3** use **CTEs** to shrink data before final aggregation; **Q4** reads from a **view** (`vw_hourly_frequency`) to reuse hourly counts.
  - The API first attempts the **CSV fast path** (precomputed in `SQL/data/`); otherwise it executes the **SQL fallback** with identical JSON output.
  - The browser renders maps/charts with **Leaflet** and **Chart.js**.
- **NoSQL Timetables**:
  - A batched ETL denormalizes to **one document per stop**, with an `upcoming_services` array; a 2dsphere index supports spatial queries.
  - The Mongo API exposes endpoints to list stops, list usable `(route_short_name, headsign)` pairs, and return **public‑service‑only** sorted times; the same browser renders the results.


## Data Models

### Relational model (ER summary)
- **Entities**: `agency`, `routes`, `trips`, `stops`, `stop_times`, `calendar`, `calendar_dates`, `shapes`.
- **Keys and relationships**:
  - `routes.route_id` (PK) → `trips.route_id` (FK)
  - `trips.trip_id` (PK) → `stop_times.trip_id` (FK)
  - `stops.stop_id` (PK) → `stop_times.stop_id` (FK)
  - `calendar.service_id` (PK) → `trips.service_id` (FK); `calendar_dates` apply exceptions
  - `shapes.shape_id` referenced by `trips` and/or implied by `stop_times.shape_dist_traveled`

### NoSQL model (stop‑centric timetable document)
- **Collection**: `stop_timetables`
- **Document shape (essentials)**:
  - `_id`, `stop_id`, `stop_name`, `stop_code`
  - `location: { type: "Point", coordinates: [lon, lat] }`
  - `upcoming_services: [ { route_id, route_short_name, route_long_name, trip_id, service_id, trip_headsign, departure_time }, ... ]`
- **Indexes**: 2dsphere on `location`; index on `stop_name` for lookup lists.

### SQL → NoSQL mapping (what we denormalize)
- **From `stops`** → root fields: `stop_id`, `stop_name`, `stop_code`, `stop_lat/lon → location`.
- **From `trips` + `routes`** → `upcoming_services[]`: `route_id`, `route_short_name`, `route_long_name`, `trip_id`, `service_id`, `trip_headsign`.
- **From `stop_times`** → `upcoming_services[]`: `departure_time` per trip occurrence.
- **Why this mapping**: it matches the operational question “show me usable public trips from stop X, grouped by route and direction, with sorted times” with a **single‑document** fetch and light in‑app grouping—no repeated joins.

---

## Key Queries & Insights (Q1–Q4)

Below, each query is summarized in plain English, connected to the schema, with notes on performance and findings. All four complete in **under six seconds** on the full dataset after indexing and query tuning. Where present, CSV caches guarantee instantaneous returns during demos.

### Q1 — Busiest stops (highest trip event counts)
- **Question (reality)**: Which stops are most active during a selected day type? This approximates passenger interchange and operational load.
- **What we compute**: For each `stop_id`, we count total `stop_times` (trip events) and the number of distinct `route_id`s that hit the stop.
- **Tables used**: `stop_times` (driver of cardinality), `trips` (to filter by `service_id`), `stops` (names and coordinates).
- **Query shape**:
  - Join `stop_times → trips` first and push `service_id` filter early to cut the search space.
  - Join to `stops` after filtering, then `GROUP BY stop_id`, compute counts, `ORDER BY` trip events, and apply `LIMIT`.
- **Performance choices**:
  - Indexes: `stop_times(trip_id)`, `stop_times(stop_id)`, `trips(service_id)`.
  - Early filter on `service_id` + `LIMIT` keeps CPU and memory stable.
- **Findings**:
  - Clusters of busiest stops appear in **downtown Toronto** and **Scarborough**.
  - Kennedy Station area, Scarborough Centre, and central corridors along Queen/King rank very high by total trip events and unique routes.
- **Presentation**: Map markers colored green→red by trip events; table lists stop name/code, total events, and unique routes.

### Q2 — Route duration and speed (ranked by highest average duration)
- **Question (reality)**: Which routes take the longest on average, and what speeds do they achieve? This diagnoses operational patterns and congestion.
- **What we compute**: A **CTE** builds per‑trip statistics: duration (`MAX(arrival_time) − MIN(departure_time)`) and distance (`MAX(shape_dist_traveled) − MIN(shape_dist_traveled)`), filtered to trips longer than 60 seconds. We then aggregate per route (and per day type when selected) to produce average duration, speed, distance, and counts.
- **Tables used**: `stop_times`, `trips`, `routes` (with distances derived from `shape_dist_traveled`).
- **Performance choices**:
  - **CTE** reduces cardinality before route aggregation.
  - Composite index `stop_times(trip_id, departure_time)` accelerates min/max scans by trip.
- **Findings**:
  - Overall averages are in the **~33–36 minutes** range with speeds **~18–19 km/h** (depending on day type and selected limit).
  - Longest individual routes exceed **90 km**, but **average speeds remain modest**, reflecting frequent stops and traffic conditions.
- **Presentation**: A banner shows overall averages; charts rank routes by duration and speed; tables list totals and averages.

### Q3 — Transfer points (stops with ≥2 unique routes)
- **Question (reality)**: Where can riders transfer between two or more distinct routes?
- **What we compute**: A **CTE** `UniqueStopRoutes` materializes distinct `(stop_id, route_id)` pairs (with `service_id` filter pushed inside), then we count the number of unique routes per stop. We keep only stops where `num_unique_routes ≥ 2` and order by that count.
- **Tables used**: `stop_times`, `trips`, `stops`.
- **Performance choices**:
  - The DISTINCT inside the CTE massively shrinks rows before the final group-by, preventing timeouts and keeping runtime under our sub‑6‑second target.
  - Indexes on `stop_times(trip_id)` and `trips(service_id)` support the CTE filter and join.
- **Findings**:
  - Major transfer clusters align with **Wilson Avenue** and **Eglinton Avenue**.
  - High counts also appear along dense downtown corridors and at key stations in Scarborough and North York.
- **Presentation**: Transfer points visualized as map dots (colored by unique route count) and a sortable table.

### Q4 — Service frequency (hourly new trips; total trips per route)
- **Question (reality)**: How intense is service by hour and by day type? Which routes have the most trips per day?
- **What we compute**: A reusable **view** `vw_hourly_frequency` counts distinct trips starting in each hour for `(route_id, service_id, hour_of_day)`. The query then sums hourly counts to daily totals and ranks the top routes;
  in whole‑week mode we also show Weekday/Sat/Sun per‑day totals and their average.
- **Tables used**: view `vw_hourly_frequency` (derived from `stop_times` + `trips`) and `routes` for naming.
- **Performance choices**:
  - Precomputation in a view ensures that downstream ranking and listing are simple and fast.
  - API ensures the view exists at startup; CSVs mirror the exact structure.
- **Findings**:
  - **504 — KING** is the highest‑frequency route with approximately **1,316 daily trips** (average across weekday, Saturday, Sunday).
  - System‑wide totals (from the dataset export): Weekday **61,390**; Saturday **50,884** (−**17.1%** vs weekday); Sunday **45,087** (−**26.6%** vs weekday). Weekend average ≈ **47,986** (−**21.8%** overall).
- **Presentation**: Hourly bar charts per route; tables with weekday/weekend totals and averages or, when showing a single day type, concise hourly profiles.

---

## Technical Highlights (Design for Scale and Clarity)

- **Indexing strategy (relational)**
  - **On `trips`**: `route_id`, `service_id` — accelerates route filters and day‑type filters.
  - **On `stop_times`**: `trip_id` and `stop_id` — the essential joins for Q1–Q3; plus a composite `(trip_id, departure_time)` for Q2’s min/max scans.
  - **On `stops`**: optional index on `stop_name` to speed lists.

- **CTEs where they matter**
  - **Q2**: `trip_stats` computes per‑trip duration and distance once; aggregates afterwards.
  - **Q3**: `UniqueStopRoutes` de‑duplicates `(stop, route)` before counting, minimizing work.

- **View for heavy reuse**
  - **Q4**: `vw_hourly_frequency` materializes the expensive step—counting distinct trips per hour—so listing and ranking are quick and composable.

- **Filter ordering and scope reduction**
  - Push `service_id` filters as early as possible (inside CTEs and WHERE clauses before joins to `stops`).
  - Rank and **`LIMIT`** late to avoid materializing excessively large intermediate results.

- **CSV fast path**
  - Precomputed CSVs for Q1–Q4 accelerate local demos and ensure reproducible poster numbers; endpoints serve CSVs if present and otherwise fall back to SQL, with the same JSON structure.

- **NoSQL fit for timetables**
  - Denormalized, stop‑centric documents resolve a common operational UX—"show me usable trips from this stop"—with a single read and minimal CPU.
  - Endpoints filter to services {1,2,3} and exclude "NOT IN SERVICE" entries, returning neatly grouped, sorted timetables.

---

## Reflection

- **Data and reality first**
  - The most important factor in gaining insight is a **deep understanding of the real‑world service** and how the data encodes it. Decisions such as counting trips separately by day type and direction, or interpreting `shape_dist_traveled` as distance, have major analytical consequences. We validated assumptions against the GTFS standard and the GTA context before optimizing queries.

- **SQL as the system of record and analytics engine**
  - MySQL provided integrity and rich analytical capability for insights like busiest stops, transfer hubs, route duration/speed rankings, and hourly frequency. However, at full scale some operations touch a cross of **~131k trips × ~4.3M stop_times**, which can be costly even with indexes.
  - We mitigated this with **CTEs** (reducing cardinality early), a **view** (reusing precomputed hourly counts), **careful filter ordering**, and **targeted indexes**. These collectively brought every analytic to **under ~6 seconds** on full data.

- **NoSQL where document shape matches the question**
  - For stop timetables, a denormalized, stop‑centric document (one document per stop with an array of upcoming services) dramatically simplifies retrieval. After a one‑time ETL cost (**20+ minutes**), real‑time lookups are fast and predictable, avoiding repeated joins.
  - The design intentionally **limits to public services** and **excludes out‑of‑service headsigns**, aligning data results with rider expectations.
  - The lesson is broader: **document schemas should be mission‑specific**. If a new mission arises—e.g., route‑centric navigation—we would create route‑keyed documents and indexes tuned to that access path rather than forcing the current shape to fit all tasks.

- **Pragmatic performance engineering**
  - Combining strong relational design with selective precomputation (CTEs/view) and result caching (CSVs) yields both **accuracy** and **responsiveness** at large scale.
  - Using the **entire dataset** was crucial: it exposed bottlenecks early and let us validate that our techniques hold up under realistic loads.

---

## Poster‑Ready Bullet Points (copy/paste)

- **Dataset**
  - **223 routes**, **9,329 stops**, **131,140 trips**, **~4.3M stop_times**.
  - Trips are unique per day type and direction.
  - Entire dataset used to evaluate performance.

- **Architecture**
  - MySQL as system of record; CSV acceleration; MongoDB for timetables.
  - Analytics via Flask endpoints; denormalized timetables via a separate ETL.

- **Indexes & SQL techniques**
  - `trips(route_id)`, `trips(service_id)`; `stop_times(trip_id)`, `stop_times(stop_id)`, `stop_times(trip_id, departure_time)`.
  - CTEs in **Q2** (per‑trip stats) and **Q3** (unique stop‑route pairs).
  - **Q4 view**: `vw_hourly_frequency` for trips per hour.

- **Performance**
  - All analytics complete in **< 6 seconds** on full data after optimization.
  - CSVs provide instant responses and reproducible numbers.

- **Insights**
  - Busiest and most connected areas: **Downtown Toronto** and **Scarborough**.
  - Transfer corridors: **Wilson Ave**, **Eglinton Ave**.
  - Top route by daily trips: **504 — KING (~1,316/day)**.
  - Weekend totals vs weekday: **Sat −17.1%**, **Sun −26.6%**, **weekend avg −21.8%**.
  - Longest routes **> 90 km**; average speeds **~18–20 km/h**.

- **NoSQL timetables**
  - Stop‑centric documents with grouped, sorted times by `(route, headsign)`.
  - Only public services (1,2,3); “NOT IN SERVICE” excluded.

---

## Appendix: Reproducibility Notes

- Use the environment variables in `.env`/`env.example` to configure database connections.
- Ensure indexes (DDL scripts) are applied to the MySQL schema.
- For Q4, the server will create the view `vw_hourly_frequency` if it does not exist.
- To regenerate CSVs, run the SQL queries and export results to the `SQL/data/` directory with the expected filenames:
  - `q1_busiest_stops.csv`
  - `q2_avg_duration_speed.csv`
  - `q3_transfer_points.csv`
  - `q4_hourly_frequency.csv`
- Run the Mongo ETL script to (re)build the `stop_timetables` collection; allow **20+ minutes** for a complete load on typical dev hardware.


