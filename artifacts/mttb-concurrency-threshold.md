# MTTB Concurrency Threshold Probe (Local Dry-Run)

Generated: 2026-06-01
Mode: SOAR dry-run (no real iptables), synthetic high-risk SSH events
Environment: local dev runtime

## Results (p95 MTTB target < 1000 ms)

| Concurrency | Samples | p95 (ms) | p99 (ms) | Max (ms) | Pass <1s p95 |
|---:|---:|---:|---:|---:|:---:|
| 10 | 30 | 12.231 | 12.318 | 12.318 | Yes |
| 50 | 150 | 77.497 | 84.334 | 85.541 | Yes |
| 100 | 300 | 139.763 | 152.507 | 155.547 | Yes |
| 200 | 600 | 503.774 | 542.951 | 550.689 | Yes |
| 500 | 1500 | 781.366 | 854.153 | 871.710 | Yes |
| 600 | 1200 | 737.155 | 769.758 | 780.638 | Yes |
| 800 | 1600 | 1009.892 | 1084.423 | 1099.462 | No |
| 1000 | 2000 | 1142.026 | 1245.099 | 1270.662 | No |

## Specific Threshold Statement

- Highest tested concurrency that still keeps p95 MTTB under 1 second: **600 concurrent events**.
- At 800 concurrency, p95 crosses 1 second.

## Caveat

This is local dry-run SOAR benchmarking, not full network end-to-end live attack traffic with real firewall operations.
Use as engineering threshold estimate, then validate again on deployed DigitalOcean instance and AWS phase.