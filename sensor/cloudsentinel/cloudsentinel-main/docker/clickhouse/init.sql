CREATE TABLE IF NOT EXISTS default.cloudsentinel_events
(
    timestamp DateTime64(3, 'UTC') DEFAULT now64(3),
    eventid LowCardinality(String),
    session String,
    sensor LowCardinality(String),
    src_ip String,
    protocol LowCardinality(String),
    country_code LowCardinality(String),
    city String,
    latitude Float64,
    longitude Float64,
    hassh String,
    hasshAlgorithms String,
    cloudsentinel_risk_score UInt16,
    cloudsentinel_mitre_techniques Array(String),
    cloudsentinel_soar_action LowCardinality(String),
    event_json String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, session, eventid)
TTL toDateTime(timestamp) + INTERVAL 90 DAY;
