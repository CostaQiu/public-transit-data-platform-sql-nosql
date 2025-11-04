/*
Query: Busiest Stops Analysis (Filtered by Service ID)
Goal: Identify stops with the highest frequency of scheduled stops (total_trip_events) for a specific service type (e.g., Weekday).
Metrics: Total Trip Events, Route Diversity (num_unique_routes), and Stop Coordinates for visualization.
*/
SELECT 
    st.stop_id, 
    s.stop_name, 
    s.stop_lat, 
    s.stop_lon, 
    COUNT(*) AS total_trip_events,
    COUNT(DISTINCT t.route_id) AS num_unique_routes 
FROM stop_times st
JOIN trips t ON t.trip_id = st.trip_id
JOIN stops s ON s.stop_id = st.stop_id
WHERE t.service_id = '1' -- FILTER: Change '1' to '2' or '3' for weekend comparison
GROUP BY st.stop_id, s.stop_name, s.stop_lat, s.stop_lon
ORDER BY total_trip_events DESC
LIMIT 10;
