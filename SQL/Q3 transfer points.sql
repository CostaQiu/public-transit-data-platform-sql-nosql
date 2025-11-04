/*
Query: Identify Transfer Points (Optimized for performance)
Goal: Find stops served by two or more unique transit routes, returning coordinates for visualization.
Implementation: Uses CTE to pre-aggregate unique (stop_id, route_id) pairs to avoid query timeout.
*/
WITH UniqueStopRoutes AS (
    -- CTE: Find all unique stop_id and route_id pairs
    SELECT DISTINCT 
        st.stop_id, 
        t.route_id
    FROM stop_times st
    JOIN trips t ON t.trip_id = st.trip_id
)
-- Main Query: Join with stops and count the unique routes
SELECT 
    s.stop_id, 
    s.stop_name, 
    s.stop_lat, 
    s.stop_lon, -- Added stop coordinates
    COUNT(USR.route_id) AS num_unique_routes 
FROM stops s
JOIN UniqueStopRoutes USR ON USR.stop_id = s.stop_id
GROUP BY s.stop_id, s.stop_name, s.stop_lat, s.stop_lon
HAVING num_unique_routes >= 2 -- Filter: Only show locations with 2 or more routes
ORDER BY num_unique_routes DESC
LIMIT 20;