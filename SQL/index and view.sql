-- ----------------------------------------------------------------------
-- 1. CORE RELATIONAL INDEXES (Critical for performance)
-- ----------------------------------------------------------------------

-- trips table: Index on Foreign Key field connecting to routes
CREATE INDEX ix_trips_route_id ON trips (route_id);

-- trips table: Index on Foreign Key field connecting to calendar
CREATE INDEX ix_trips_service_id ON trips (service_id);

-- stop_times table: Index on Foreign Key field connecting to trips (Essential for all joins)
CREATE INDEX ix_stop_times_trip_id ON stop_times (trip_id);

-- stop_times table: Index on Foreign Key field connecting to stops (Essential for Busiest Stops count)
CREATE INDEX ix_stop_times_stop_id ON stop_times (stop_id);


-- ----------------------------------------------------------------------
-- 2. AUXILIARY INDEXES (For common analytical queries)
-- ----------------------------------------------------------------------

-- stop_times table: Composite index on (trip_id, departure_time) 
-- Supports fast lookups for MIN/MAX departure times for Average Trip Duration query
CREATE INDEX ix_st_trip_dep_time ON stop_times (trip_id, departure_time);

-- stops table: Index on stop_name to potentially speed up GROUP BY and result display
CREATE INDEX ix_stops_name ON stops (stop_name);