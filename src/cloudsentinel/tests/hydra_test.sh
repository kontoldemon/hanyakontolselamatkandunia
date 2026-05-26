#!/bin/bash
# ============================================================================
# CloudSentinel Hydra Brute-Force Simulation
# Phase 1: DigitalOcean Dev/MVP validation
#
# Simulates real-world SSH brute-force attack against the CloudSentinel sensor.
# Validates:
#   - HASSH fingerprint extraction
#   - MITRE T1110 (Brute Force) detection
#   - SOAR auto-blocking (iptables)
#   - MTTB measurement
#   - ClickHouse event persistence
#
# Usage:
#   chmod +x hydra_test.sh
#   ./hydra_test.sh [target_ip] [target_port]
#
# Prerequisites:
#   - hydra installed (apt install hydra)
#   - wordlists/common.txt present (or use built-in rockyou subset)
# ============================================================================

set -euo pipefail

TARGET_IP="${1:-188.166.184.42}"
TARGET_PORT="${2:-22}"
WORDLIST="${3:-../../wordlists/common.txt}"
PASSWORD_LIST="$(mktemp)"
RESULTS_FILE="hydra_results_$(date +%Y%m%d_%H%M%S).txt"
START_TIME=$(date +%s.%N)

echo "============================================"
echo " CloudSentinel Hydra Brute-Force Simulation"
echo "============================================"
echo " Target:  ${TARGET_IP}:${TARGET_PORT}"
echo " Wordlist: ${WORDLIST}"
echo " Start:   $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# Generate test password list (common brute-force passwords + CloudSentinel-specific)
cat > "$PASSWORD_LIST" << 'PWLIST'
root
admin
password
123456
12345678
qwerty
letmein
changeme
ubuntu
test
user
guest
admin123
root123
toor
default
usas2024
cloudsentinel
honeypot
PWLIST

# Check if wordlist exists
if [ ! -f "$WORDLIST" ]; then
    echo "[!] Wordlist not found: $WORDLIST"
    echo "[*] Using built-in password list (${PASSWORD_LIST})"
    WORDLIST="$PASSWORD_LIST"
fi

# Username list (common SSH brute targets)
USERNAME_LIST="$(mktemp)"
cat > "$USERNAME_LIST" << 'USERLIST'
root
admin
ubuntu
debian
pi
ec2-user
test
guest
oracle
postgres
USERLIST

echo "[*] Starting Hydra attack (10 tasks, 500ms delay between attempts)..."
echo ""

# Run Hydra with:
#   -L : username list
#   -P : password list
#   -t 10 : 10 parallel tasks
#   -w 1 : 1 second between connections (realistic pacing)
#   -V  : verbose (show each attempt)
#   -o  : output file
hydra \
    -L "$USERNAME_LIST" \
    -P "$WORDLIST" \
    -t 10 \
    -w 1 \
    -V \
    -o "$RESULTS_FILE" \
    "ssh://${TARGET_IP}:${TARGET_PORT}"

END_TIME=$(date +%s.%N)
DURATION=$(echo "$END_TIME - $START_TIME" | bc)

echo ""
echo "============================================"
echo " Hydra Attack Complete"
echo "============================================"
echo " Duration: ${DURATION}s"
echo " Results:  ${RESULTS_FILE}"
echo "============================================"
echo ""
echo "[*] Next: Check CloudSentinel dashboard for:"
echo "    1. MITRE T1110 (Brute Force) events"
echo "    2. HASSH fingerprints captured"
echo "    3. SOAR block actions triggered"
echo "    4. MTTB < 100ms per block"
echo ""
echo "[*] Run validate_phase1.py to verify metrics"
echo "    python -m cloudsentinel.validate_phase1 --host ${TARGET_IP}"

# Cleanup temp files
rm -f "$PASSWORD_LIST" "$USERNAME_LIST"
