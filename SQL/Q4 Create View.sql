-- 6A) VIEW: Create a view to pre-calculate Trips per Hour for all Routes/Services
-- Definition: Calculates the number of unique trips scheduled for each route within each hour (0 to 28+) of the day.
DROP VIEW IF EXISTS vw_hourly_frequency;
CREATE VIEW vw_hourly_frequency AS
SELECT
    t.route_id,
    t.service_id,
    HOUR(st.departure_time) AS hour_of_day, 
    COUNT(DISTINCT t.trip_id) AS trips_per_hour -- Count unique trips starting in that hour slot
FROM stop_times st
JOIN trips t ON t.trip_id = st.trip_id
-- We only need to count the trip once per hour. Grouping by the unique trip is sufficient.
GROUP BY t.route_id, t.service_id, hour_of_day
ORDER BY t.route_id, t.service_id, hour_of_day;