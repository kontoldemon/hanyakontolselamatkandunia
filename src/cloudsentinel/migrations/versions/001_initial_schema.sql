-- CloudSentinel v2.0 initial schema
-- Applied: 2026-05-25

CREATE TABLE IF NOT EXISTS cloudsentinel_events (
    eventid             LowCardinality(String),
    session             String,
    sensor              LowCardinality(String) DEFAULT 'CloudSentinel',
    src_ip              String,
    src_port            UInt16 DEFAULT 0,
    dst_ip              String DEFAULT '',
    dst_port            UInt16 DEFAULT 0,
    country_code        LowCardinality(String) DEFAULT 'XX',
    country_name        String DEFAULT '',
    city                String DEFAULT '',
    username            String DEFAULT '',
    password            String DEFAULT '',
    hassh_md5           String DEFAULT '',
    hassh_algorithms    String DEFAULT '',
    version             String DEFAULT '',
    input               String DEFAULT '',
    cloudsentinel_risk_score        UInt16 DEFAULT 0,
    cloudsentinel_mitre_techniques  Array(String) DEFAULT [],
    cloudsentinel_soar_action       LowCardinality(String) DEFAULT 'none',
    mttb_ms                         Float64 DEFAULT 0,
    timestamp           DateTime64(3) DEFAULT now64(3)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (eventid, timestamp, src_ip)
TTL timestamp + INTERVAL 3650 DAY;

CREATE TABLE IF NOT EXISTS _cloudsentinel_migrations (
    version String,
    applied_at DateTime DEFAULT now()
) ENGINE = MergeTree() ORDER BY version;
