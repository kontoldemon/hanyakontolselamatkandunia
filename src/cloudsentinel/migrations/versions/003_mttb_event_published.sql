DROP VIEW IF EXISTS cloudsentinel_mttb_stats;

CREATE MATERIALIZED VIEW cloudsentinel_mttb_stats
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
WHERE mttb_ms > 0 AND cloudsentinel_soar_action IN ('iptables_block', 'dry_run_block', 'event_published')
GROUP BY hour;
