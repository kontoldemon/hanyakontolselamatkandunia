-- ============================================================================
-- CloudSentinel ClickHouse Schema
-- Phase 1: Dev/MVP on DigitalOcean
-- Engine: MergeTree for time-series analytics
-- ============================================================================

-- Main events table - all CloudSentinel audit events
CREATE TABLE IF NOT EXISTS cloudsentinel_events (
    -- Identifiers
    eventid             LowCardinality(String),
    session             String,
    sensor              LowCardinality(String) DEFAULT 'CloudSentinel',

    -- Network
    src_ip              String,
    src_port            UInt16 DEFAULT 0,
    dst_ip              String DEFAULT '',
    dst_port            UInt16 DEFAULT 0,

    -- Geolocation
    country_code        LowCardinality(String) DEFAULT 'XX',
    country_name        String DEFAULT '',
    city                String DEFAULT '',
    continent           LowCardinality(String) DEFAULT 'XX',
    latitude            String DEFAULT '0',
    longitude           String DEFAULT '0',
    timezone            String DEFAULT 'UTC',

    -- Authentication
    username            String DEFAULT '',
    password            String DEFAULT '',
    auth_type           LowCardinality(String) DEFAULT 'password',
    attempt             UInt16 DEFAULT 0,

    -- HASSH fingerprinting
    hassh_md5           String DEFAULT '',
    hassh_algorithms    String DEFAULT '',
    kexAlgs             Array(String) DEFAULT [],
    encCS               Array(String) DEFAULT [],
    macCS               Array(String) DEFAULT [],
    compCS              Array(String) DEFAULT [],

    -- SSH client
    version             String DEFAULT '',
    key_type            String DEFAULT '',

    -- Command execution
    input               String DEFAULT '',
    reason              String DEFAULT '',

    -- CloudSentinel SOAR annotations
    cloudsentinel_risk_score        UInt16 DEFAULT 0,
    cloudsentinel_mitre_techniques  Array(String) DEFAULT [],
    cloudsentinel_soar_action       LowCardinality(String) DEFAULT 'none',
    detected_at                     DateTime64(3) DEFAULT toDateTime64(0, 3),
    block_started_at                DateTime64(3) DEFAULT toDateTime64(0, 3),
    block_completed_at              DateTime64(3) DEFAULT toDateTime64(0, 3),
    mttb_ms                         Float64 DEFAULT 0,
    block_command                   String DEFAULT '',
    block_stdout                    String DEFAULT '',
    block_stderr                    String DEFAULT '',

    -- Timing
    duration            String DEFAULT '',
    timestamp           DateTime64(3) DEFAULT now64(3)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (eventid, timestamp, src_ip)
TTL timestamp + INTERVAL 3650 DAY
SETTINGS index_granularity = 8192;

ALTER TABLE cloudsentinel_events ADD COLUMN IF NOT EXISTS detected_at DateTime64(3) DEFAULT toDateTime64(0, 3);
ALTER TABLE cloudsentinel_events ADD COLUMN IF NOT EXISTS block_started_at DateTime64(3) DEFAULT toDateTime64(0, 3);
ALTER TABLE cloudsentinel_events ADD COLUMN IF NOT EXISTS block_completed_at DateTime64(3) DEFAULT toDateTime64(0, 3);
ALTER TABLE cloudsentinel_events ADD COLUMN IF NOT EXISTS mttb_ms Float64 DEFAULT 0;
ALTER TABLE cloudsentinel_events ADD COLUMN IF NOT EXISTS block_command String DEFAULT '';
ALTER TABLE cloudsentinel_events ADD COLUMN IF NOT EXISTS block_stdout String DEFAULT '';
ALTER TABLE cloudsentinel_events ADD COLUMN IF NOT EXISTS block_stderr String DEFAULT '';

-- HASSH DNA table - identity-centric threat intelligence
CREATE TABLE IF NOT EXISTS cloudsentinel_hassh_dna (
    hassh_md5           String,
    client_software     String DEFAULT 'unknown',
    botnet_family       LowCardinality(String) DEFAULT 'unknown',
    threat_level        LowCardinality(String) DEFAULT 'unknown',
    first_seen          DateTime64(3) DEFAULT now64(3),
    last_seen           DateTime64(3) DEFAULT now64(3),
    sighting_count      UInt64 DEFAULT 1,
    tags                Array(String) DEFAULT []
)
ENGINE = ReplacingMergeTree()
ORDER BY hassh_md5
SETTINGS index_granularity = 256;

-- Materialized view: real-time attack type distribution
CREATE MATERIALIZED VIEW IF NOT EXISTS cloudsentinel_attack_distribution
ENGINE = SummingMergeTree()
ORDER BY (eventid, country_code)
AS SELECT
    eventid,
    country_code,
    count() as event_count
FROM cloudsentinel_events
WHERE eventid IN (
    'cloudsentinel.command.input',
    'cloudsentinel.login.failed',
    'cloudsentinel.login.success',
    'cloudsentinel.session.connect'
)
GROUP BY eventid, country_code;

-- Materialized view: MITRE TTP aggregation
CREATE MATERIALIZED VIEW IF NOT EXISTS cloudsentinel_mitre_stats
ENGINE = SummingMergeTree()
ORDER BY (technique, country_code)
AS SELECT
    arrayJoin(cloudsentinel_mitre_techniques) as technique,
    country_code,
    count() as hit_count
FROM cloudsentinel_events
WHERE length(cloudsentinel_mitre_techniques) > 0
GROUP BY technique, country_code;

-- Materialized view: hourly attack volume
CREATE MATERIALIZED VIEW IF NOT EXISTS cloudsentinel_hourly_volume
ENGINE = SummingMergeTree()
ORDER BY (hour, src_ip)
AS SELECT
    toStartOfHour(timestamp) as hour,
    src_ip,
    country_code,
    count() as attempts
FROM cloudsentinel_events
WHERE eventid IN ('cloudsentinel.login.failed', 'cloudsentinel.session.connect')
GROUP BY hour, src_ip, country_code;

-- Materialized view: MTTB performance percentiles (p50, p95, p99)
CREATE MATERIALIZED VIEW IF NOT EXISTS cloudsentinel_mttb_stats
ENGINE = AggregatingMergeTree()
ORDER BY (hour)
AS SELECT
    toStartOfHour(timestamp) as hour,
    quantile(0.50)(mttb_ms) as mttb_p50_ms,
    quantile(0.95)(mttb_ms) as mttb_p95_ms,
    quantile(0.99)(mttb_ms) as mttb_p99_ms,
    avg(mttb_ms) as mttb_avg_ms,
    count() as total_blocks
FROM cloudsentinel_events
WHERE mttb_ms > 0 AND cloudsentinel_soar_action IN ('iptables_block', 'dry_run_block')
GROUP BY hour;

-- Materialized view: top attacker IPs (24h rolling)
CREATE MATERIALIZED VIEW IF NOT EXISTS cloudsentinel_top_attackers
ENGINE = SummingMergeTree()
ORDER BY (day, src_ip)
AS SELECT
    toStartOfDay(timestamp) as day,
    src_ip,
    country_code,
    count() as total_events,
    uniq(eventid) as unique_event_types,
    max(cloudsentinel_risk_score) as max_risk,
    groupArray(10)(cloudsentinel_mitre_techniques) as top_techniques
FROM cloudsentinel_events
WHERE country_code != 'XX'
GROUP BY day, src_ip, country_code;
