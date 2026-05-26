# CloudSentinel WireGuard Secure Tunnel

Encrypted management channel between the sensor node and the War Room dashboard.

## Setup

### 1. Generate keys on sensor
```bash
wg genkey | tee sensor_private.key | wg pubkey > sensor_public.key
```

### 2. Generate keys on dashboard
```bash
wg genkey | tee dashboard_private.key | wg pubkey > dashboard_public.key
```

### 3. Replace placeholders in wg-server.conf and wg-client.conf

### 4. Start tunnel
```bash
# Sensor
wg-quick up ./wg-server.conf

# Dashboard
wg-quick up ./wg-client.conf
```

### 5. Update ClickHouse connection
After tunnel is up, use `10.99.0.1:8123` instead of public IP for ClickHouse queries.

### 6. Update admin API URL
Dashboard connects to `http://10.99.0.1:8080` for admin API calls.
