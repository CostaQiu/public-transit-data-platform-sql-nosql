/*
Query: Extended Trip Duration and Speed Analysis (Service ID 1)
Goal: Calculate the average distance, duration, and speed for each route.
Metrics: avg_duration, avg_trip_distance, avg_speed, duration_stddev.
New Requirement: Added 'total_trips' count for the route under this service ID.
*/
WITH trip_stats AS (
    -- CTE: Calculates statistics for each individual trip, filtering out zero-duration trips.
    SELECT
        t.route_id,
        t.service_id, 
        TIMESTAMPDIFF(SECOND, MIN(st.departure_time), MAX(st.arrival_time)) AS trip_duration_seconds,
        (MAX(st.shape_dist_traveled) - MIN(st.shape_dist_traveled)) AS trip_distance 
    FROM stop_times st
    JOIN trips t ON t.trip_id = st.trip_id
    GROUP BY t.trip_id, t.route_id, t.service_id
    HAVING trip_duration_seconds > 60 -- Data Quality: Filters out trips shorter than 60 seconds
)
SELECT
    r.route_long_name,
    ts.service_id,
    COUNT(ts.route_id) AS total_trips_on_service, -- New Field: Total trips for this route/service
    AVG(ts.trip_distance) AS avg_trip_distance_km, 
    AVG(ts.trip_duration_seconds) / 60.0 AS avg_duration_min,
    STDDEV(ts.trip_duration_seconds) / 60.0 AS duration_stddev_min, 
    AVG(ts.trip_distance / NULLIF(ts.trip_duration_seconds, 0) * 3600) AS avg_speed_kmh 
FROM trip_stats ts
JOIN routes r ON r.route_id = ts.route_id
WHERE ts.service_id = '1' -- FILTER: Analyze only Workday (Service ID 1) trips
GROUP BY r.route_long_name, ts.service_id
ORDER BY avg_duration_min DESC
LIMIT 20;


-- Visualization Helper (For a specific route from the results above):
/*
Goal: Retrieve all ordered stop coordinates for a single route (e.g., 'QUEEN' route, Service ID 1) for Folium visualization.
Implementation: Finds the longest trip_id for the specified route/service to represent the full path.
*/
WITH LongestTrip AS (
    SELECT
        t.trip_id
    FROM trips t
    JOIN routes r ON r.route_id = t.route_id
    WHERE r.route_long_name = 'QUEEN' AND t.service_id = '1'
    GROUP BY t.trip_id
    ORDER BY COUNT(*) DESC -- Find the trip with the most stops (likely the full path)
    LIMIT 1
)
SELECT 
    s.stop_lat, 
    s.stop_lon, 
    st.stop_sequence
FROM stop_times st
JOIN stops s ON s.stop_id = st.stop_id
WHERE st.trip_id = (SELECT trip_id FROM LongestTrip)
ORDER BY st.stop_sequence;