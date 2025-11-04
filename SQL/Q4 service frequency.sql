-- 6A) VIEW: Create a view to pre-calculate Trips per Hour for all Routes/Services
-- Definition: Calculates the number of unique trips scheduled for each route within each hour (0 to 28+) of the day.
DROP VIEW IF EXISTS vw_hourly_frequency;
CREATE VIEW vw_hourly_frequency AS
SELECT
    t.route_id,
    t.service_id,
    HOUR(st.departure_time) AS hour_of_day, 
    COUNT(DISTINCT t.trip_id) AS trips_per_hour -- KEY: Count unique trips that depart in that hour slot
FROM stop_times st
JOIN trips t ON t.trip_id = st.trip_id
-- Grouping by trip_id, route_id, service_id, and hour_of_day ensures accurate counts
GROUP BY t.route_id, t.service_id, hour_of_day
ORDER BY t.route_id, t.service_id, hour_of_day;

-- 6B) QUERY: Query the View to show hourly breakdown and full-day total
-- Goal: Show the hourly service pattern AND the total daily unique trips for each route.
SELECT
    r.route_long_name,
    vhf.service_id,
    -- Display the hourly frequency profile
    GROUP_CONCAT(CONCAT(vhf.hour_of_day, ':', vhf.trips_per_hour) ORDER BY vhf.hour_of_day SEPARATOR ' | ') AS hourly_frequency_profile,
    -- Sum the hourly counts to get the total number of trips for the entire service day
    SUM(vhf.trips_per_hour) AS total_daily_trips_for_route 
    -- NOTE: Since the VIEW already counted DISTINCT trips per hour, summing them gives the total trips for the route.
FROM vw_hourly_frequency vhf
JOIN routes r ON r.route_id = vhf.route_id
WHERE vhf.service_id = '1' -- FILTER: Change service_id as needed
GROUP BY r.route_long_name, vhf.service_id
ORDER BY total_daily_trips_for_route DESC
LIMIT 10;