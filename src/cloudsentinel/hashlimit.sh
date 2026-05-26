#!/usr/bin/env bash
# ============================================================================
# CloudSentinel Kernel-Level Rate Limiting (iptables hashlimit)
# Protects the sensor from botnet floods at the kernel level, before packets
# reach the Python event loop.
#
# Usage: sudo ./hashlimit.sh [--apply] [--remove]
# ============================================================================

set -euo pipefail

HONEYPOT_PORT="${HONEYPOT_PORT:-22}"
MGMT_PORT="${MGMT_PORT:-22222}"

# hashlimit: 60 new connections per minute per source IP, burst 10
# This is kernel-level, so it handles 10,000+ IPs without touching Python.
HASHLIMIT_RULE=(
    -p tcp --dport "${HONEYPOT_PORT}"
    -m state --state NEW
    -m hashlimit
    --hashlimit-name cloudsentinel_conn
    --hashlimit-above 60/minute
    --hashlimit-burst 10
    --hashlimit-mode srcip
    -j DROP
)

apply() {
    echo "[+] Applying kernel-level hashlimit for port ${HONEYPOT_PORT}..."

    # Check if rule already exists
    if iptables -C INPUT "${HASHLIMIT_RULE[@]}" 2>/dev/null; then
        echo "    Rule already exists, skipping."
    else
        iptables -A INPUT "${HASHLIMIT_RULE[@]}"
        echo "    Rule added: max 60 conn/min per IP, burst 10"
    fi

    # Whitelist management port explicitly
    iptables -C INPUT -p tcp --dport "${MGMT_PORT}" -j ACCEPT 2>/dev/null || \
        iptables -I INPUT 1 -p tcp --dport "${MGMT_PORT}" -j ACCEPT

    # Whitelist established connections
    iptables -C INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || \
        iptables -I INPUT 1 -m state --state ESTABLISHED,RELATED -j ACCEPT

    # Save rules
    if command -v iptables-save &>/dev/null; then
        iptables-save > /etc/iptables/rules.v4 2>/dev/null || \
            iptables-save > /etc/sysconfig/iptables 2>/dev/null || true
    fi

    echo "[+] Kernel-level rate limiting active."
    echo "    Stats: iptables -L INPUT -v -n | grep hashlimit"
}

remove() {
    echo "[-] Removing kernel-level hashlimit..."
    iptables -D INPUT "${HASHLIMIT_RULE[@]}" 2>/dev/null || echo "    Rule not found."
}

status() {
    echo "[*] Current hashlimit rules:"
    iptables -L INPUT -v -n 2>/dev/null | grep -i hashlimit || echo "    None"
}

case "${1:-}" in
    --apply|apply)
        if [ "${EUID:-0}" -ne 0 ]; then echo "Run as root."; exit 1; fi
        apply
        ;;
    --remove|remove)
        if [ "${EUID:-0}" -ne 0 ]; then echo "Run as root."; exit 1; fi
        remove
        ;;
    --status|status)
        if [ "${EUID:-0}" -ne 0 ]; then echo "Run as root."; exit 1; fi
        status
        ;;
    *)
        echo "Usage: $0 [--apply|--remove|--status]"
        echo ""
        echo "  --apply   Install kernel-level rate limiting (60 conn/min per IP)"
        echo "  --remove  Remove rate limiting rules"
        echo "  --status  Show current hashlimit rules"
        ;;
esac
