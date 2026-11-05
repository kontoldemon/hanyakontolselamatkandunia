-- Extend retention for existing ClickHouse deployments.
-- New deployments already create the table with a 3650 day TTL.

ALTER TABLE cloudsentinel_events
    MODIFY TTL timestamp + INTERVAL 3650 DAY;
