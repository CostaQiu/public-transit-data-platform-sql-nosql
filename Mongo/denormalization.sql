SELECT
    st.stop_id,
    s.stop_name,
    s.stop_lat,
    s.stop_lon,
    r.route_id,
    r.route_short_name,
    r.route_long_name,
    t.trip_id,
    t.service_id,
    t.trip_headsign,
    st.departure_time
FROM stop_times st 
USE INDEX (ix_stop_times_trip_id) -- Force use of the critical index
JOIN stops s ON s.stop_id = st.stop_id
JOIN trips t ON t.trip_id = st.trip_id
JOIN routes r ON r.route_id = t.route_id
ORDER BY st.stop_id, st.departure_time; -- Order is crucial for Python processing