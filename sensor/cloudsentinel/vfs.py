"""CloudSentinel VFS - pickle loader, /proc stubs, and OS deception."""

from __future__ import annotations

import json
import os
import pickle
import time
from pathlib import Path
from typing import Any


DEFAULT_PROFILES = {
    "ubuntu-22.04": {
        "cpuinfo": b"processor\t: 0\nvendor_id\t: GenuineIntel\ncpu family\t: 6\nmodel\t\t: 85\nmodel name\t: Intel(R) Xeon(R) Platinum 8259CL CPU @ 2.50GHz\ncpu MHz\t\t: 2499.999\ncache size\t: 36608 KB\nsiblings\t: 4\ncpu cores\t: 4\n",
        "meminfo": b"MemTotal:        4026348 kB\nMemFree:         2765368 kB\nMemAvailable:    3195124 kB\nSwapTotal:       1048572 kB\nSwapFree:        1048572 kB\n",
        "version": b"Linux version 5.15.0-97-generic (buildd@lcy02-amd64-101) #107-Ubuntu SMP Thu Feb 15 15:00:00 UTC 2024\n",
        "os_release": b'PRETTY_NAME="Ubuntu 22.04.5 LTS"\nNAME="Ubuntu"\nVERSION_ID="22.04"\nVERSION="22.04.5 LTS (Jammy Jellyfish)"\nVERSION_CODENAME=jammy\nID=ubuntu\nID_LIKE=debian\n',
        "issue": b"Ubuntu 22.04.5 LTS \\n \\l\n",
        "issue_net": b"USAS Production Server v01\nAuthorized access only. All activities are monitored.\n",
        "motd_prefix": b"Welcome to Ubuntu 22.04.5 LTS\n\nSystem information as of ",
    },
    "alpine-3.18": {
        "cpuinfo": b"processor\t: 0\nvendor_id\t: AuthenticAMD\ncpu family\t: 23\nmodel\t\t: 49\nmodel name\t: AMD EPYC 7002 Processor\ncpu MHz\t\t: 2500.000\ncache size\t: 512 KB\nsiblings\t: 1\ncpu cores\t: 1\n",
        "meminfo": b"MemTotal:        1024000 kB\nMemFree:         512000 kB\nMemAvailable:    800000 kB\nSwapTotal:       0 kB\nSwapFree:        0 kB\n",
        "version": b"Linux version 6.1.77-0-lts (buildozer@build-3-18-x86_64) #1-Alpine SMP PREEMPT_RT Mon, 29 Jan 2024 10:48:47 +0000\n",
        "os_release": b'NAME="Alpine Linux"\nID=alpine\nVERSION_ID=3.18.6\nPRETTY_NAME="Alpine Linux v3.18"\nHOME_URL="https://alpinelinux.org/"\nBUG_REPORT_URL="https://gitlab.alpinelinux.org/alpine/aports/-/issues"\n',
        "issue": b"Welcome to Alpine Linux 3.18\nKernel \\r on an \\m (\\l)\n",
        "issue_net": b"Welcome to Alpine Linux 3.18\n",
        "motd_prefix": b"Welcome to Alpine!\n\nSystem information as of ",
    }
}


class VirtualFileSystem:
    def __init__(self, os_profile_name: str = "ubuntu-22.04") -> None:
        self._entries: dict[str, dict[str, Any]] = {}
        self._mtime_base: float = time.time()
        self.os_profile = DEFAULT_PROFILES.get(os_profile_name, DEFAULT_PROFILES["ubuntu-22.04"])

    @staticmethod
    def resolve_path(path: str, cwd: str) -> str:
        if path.startswith("/"): resolved = path
        else: resolved = f"{cwd.rstrip('/')}/{path}"
        parts = []
        for part in resolved.split("/"):
            if part in ("", "."): continue
            if part == "..":
                if parts: parts.pop()
            else: parts.append(part)
        return "/" + "/".join(parts)

    def exists(self, path: str) -> bool: return path in self._entries
    def isdir(self, path: str) -> bool:
        e = self._entries.get(path); return e is not None and e.get("type") == "dir"
    def isfile(self, path: str) -> bool:
        e = self._entries.get(path); return e is not None and e.get("type") == "file"

    def mkdir(self, path: str, uid: int = 0, gid: int = 0, size: int = 4096, mode: int = 0o755) -> None:
        self._entries[path] = {"type": "dir", "uid": uid, "gid": gid, "size": size, "mode": mode, "mtime": time.time() - self._mtime_base, "content": None}

    def mkfile(self, path: str, content: bytes = b"", uid: int = 0, gid: int = 0, mode: int = 0o644) -> None:
        self._entries[path] = {"type": "file", "uid": uid, "gid": gid, "size": len(content), "mode": mode, "mtime": time.time() - self._mtime_base, "content": content}

    def listdir(self, path: str) -> list[str]:
        path = path.rstrip("/") or "/"
        prefix = path if path == "/" else path + "/"
        results = []
        for ep in self._entries:
            if ep == path: continue
            if ep.startswith(prefix):
                rel = ep[len(prefix):]
                if "/" not in rel: results.append(rel)
        return results

    def file_contents(self, path: str) -> bytes:
        e = self._entries.get(path)
        if e is None: raise KeyError(path)
        if e.get("type") != "file": raise IsADirectoryError(path)
        return e.get("content", b"")

    def stat(self, path: str) -> dict | None: return self._entries.get(path)

    @classmethod
    def from_pickle(cls, pickle_path: str, os_profile_name: str = "ubuntu-22.04") -> VirtualFileSystem:
        vfs = cls(os_profile_name)
        with open(pickle_path, "rb") as fh:
            data = pickle.load(fh)
        if isinstance(data, dict): vfs._entries = data
        return vfs

    @classmethod
    def from_honeyfs(cls, honeyfs_root: str, os_profile_name: str = "ubuntu-22.04") -> VirtualFileSystem:
        vfs = cls(os_profile_name); root = Path(honeyfs_root)
        if not root.is_dir(): return vfs
        vfs.mkdir("/")
        for entry in root.rglob("*"):
            rel = "/" + entry.relative_to(root).as_posix()
            if entry.is_dir(): vfs.mkdir(rel)
            elif entry.is_file():
                try: content = entry.read_bytes()
                except OSError: content = b""
                vfs.mkfile(rel, content)
        return vfs

    @classmethod
    def build_default(cls, data_dir: str | None = None, os_profile_name: str = "ubuntu-22.04") -> VirtualFileSystem:
        # 1. Try CloudSentinel pickle.
        for candidate in [
            Path(__file__).parent / "cloudsentinel-main" / "var" / "lib" / "cloudsentinel" / "fs.pickle",
            Path("/var/lib/cloudsentinel/fs.pickle"),
        ]:
            if candidate.exists():
                vfs = cls.from_pickle(str(candidate), os_profile_name)
                vfs._add_proc_stubs()
                return vfs

        # 2. Try honeyfs directory
        for candidate in [
            Path(__file__).parent / "cloudsentinel-main" / "honeyfs",
        ]:
            if candidate.is_dir():
                vfs = cls.from_honeyfs(str(candidate), os_profile_name)
                vfs._add_proc_stubs()
                return vfs

        # 3. Built-in minimal
        return cls._build_minimal(os_profile_name)

    def _add_proc_stubs(self) -> None:
        self.mkdir("/proc"); self.mkdir("/sys"); self.mkdir("/dev")
        self.mkfile("/proc/cpuinfo", self.os_profile["cpuinfo"])
        self.mkfile("/proc/meminfo", self.os_profile["meminfo"])
        self.mkfile("/proc/version", self.os_profile["version"])
        self.mkfile("/proc/loadavg", b"0.08 0.12 0.09 1/156 18423\n")
        self.mkfile("/proc/uptime", b"604800.00 602400.00\n")
        self.mkfile("/dev/null", b""); self.mkfile("/dev/urandom", b""); self.mkfile("/dev/zero", b"")
        # Network /proc stubs
        self.mkfile("/proc/net/tcp", b"  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n   0: 00000000:08AE 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 12345 1 0000000000000000 100 0 0 10 0\n")
        self.mkfile("/proc/net/arp", b"IP address       HW type     Flags       HW address            Mask     Device\n10.0.0.1         0x1         0x2         00:00:00:00:00:01     *        eth0\n")
        # Dotfiles
        self.mkdir("/root"); self.mkdir("/root/.ssh")
        self.mkfile("/root/.bash_history", b"ls -la\ncd /var/tmp\nuname -a\ncat /etc/passwd\nwhoami\nps aux\nexit\n")
        self.mkfile("/root/.ssh/authorized_keys", b"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC admin@usas-internal\n")
        # Fake log files
        self.mkdir("/var/log")
        self.mkfile("/var/log/auth.log", b"Jan 15 12:00:00 usas-prod-srv-01 sshd[423]: Accepted publickey for root from 10.0.0.1 port 54321 ssh2: RSA SHA256:abcdef\nJan 15 12:05:00 usas-prod-srv-01 sshd[512]: Accepted password for admin from 192.168.1.100 port 12345 ssh2\n")
        # Fake crontab
        self.mkdir("/etc"); self.mkfile("/etc/crontab", b"# /etc/crontab: system-wide crontab\nSHELL=/bin/sh\nPATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin\n17 *    * * *   root    cd / && run-parts --report /etc/cron.hourly\n25 6    * * *   root    test -x /usr/sbin/anacron || { cd / && run-parts --report /etc/cron.daily; }\n47 6    * * 7   root    test -x /usr/sbin/anacron || { cd / && run-parts --report /etc/cron.weekly; }\n52 6    1 * *   root    test -x /usr/sbin/anacron || { cd / && run-parts --report /etc/cron.monthly; }\n0 2 * * * root /usr/bin/backup.sh >> /var/log/backup.log 2>&1\n")

        # ── Rich deception files (honeytokens, credentials, internal topology) ──
        self.mkfile("/etc/hosts", b"127.0.0.1 localhost\n10.0.0.4 usas-prod-srv-01 usas-prod-srv-01.internal\n10.0.0.5 usas-db-01.internal\n10.0.0.6 usas-app-02.internal\n10.12.4.18 backup-nas.internal\n")
        self.mkfile("/etc/resolv.conf", b"nameserver 10.0.0.2\nsearch internal.usas.edu.my\n")
        self.mkdir("/etc/ssh")
        self.mkfile("/etc/ssh/sshd_config", b"Port 22\nPermitRootLogin yes\nPasswordAuthentication yes\nPubkeyAuthentication yes\nAuthorizedKeysFile .ssh/authorized_keys\n")
        self.mkfile("/root/.ssh/id_rsa", b"-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABlwAAAAdzc2gtcn\nNhAAAAAwEAAQAAAYEAv7xTQ2M8kXK1P9ZzGvLm8xJ3dV5YwWmAQRtC2nV7eBgHM9pL\n-----END OPENSSH PRIVATE KEY-----\n")
        self.mkfile("/root/.ssh/id_rsa.pub", b"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC/vFNDYzyRcrU/1nMa8ubzEnd1XljBaYBBG0LadXt4GAcz2ks= admin@usas-internal\n")
        self.mkfile("/root/.ssh/known_hosts", b"|1|abc123=|def456= ssh-rsa AAAAB3NzaC1yc2E... usas-db-01.internal\n")
        self.mkfile("/root/.mysql_history", b"mysql -u root -p\nUSE usas_production;\nSELECT * FROM users WHERE role=\'admin\';\nSHOW DATABASES;\nexit\n")
        self.mkfile("/root/backup.sh", b"#!/bin/bash\n# USAS Automated Backup Script\nmysqldump -u backup -p\'b4ckup_p4ss_2024\' usas_production > /mnt/backup/usas_db_$(date +%Y%m%d).sql\ntar -czf /mnt/backup/usas_app_$(date +%Y%m%d).tar.gz /var/www/html\n")
        self.mkdir("/root/.aws")
        self.mkfile("/root/.aws/credentials", b"[default]\naws_access_key_id = AKIAIOSFODNN7EXAMPLE\naws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\nregion = ap-southeast-1\n")
        self.mkdir("/var/www"); self.mkdir("/var/www/html")
        self.mkfile("/var/www/html/config.php", b"<?php\n$db_host = \'10.0.0.5\';\n$db_user = \'usas_app\';\n$db_pass = \'Ch4ng3M3_N0w!_2024\';\n$db_name = \'usas_production\';\n?>\n")
        self.mkdir("/etc/mysql")
        self.mkfile("/etc/mysql/my.cnf", b"[mysqld]\nbind-address = 0.0.0.0\nport = 3306\nuser = mysql\npid-file = /var/run/mysqld/mysqld.pid\n")
        self.mkfile("/var/log/backup.log", b"[2024-01-15 02:00:01] Starting backup...\n[2024-01-15 02:00:05] Database dump complete: 234MB\n[2024-01-15 02:00:08] App files archived: 456MB\n[2024-01-15 02:00:12] Backup transferred to backup-nas.internal\n")
        self.mkfile("/root/usas_backup_credentials.txt", b"backup_user=usas_backup\nbackup_pass=Backup!2024!Secure\nbackup_host=10.12.4.18\nrotation=quarterly\n")
        self.mkfile("/root/research_grants_2026.txt", b"USAS Research Grants 2026\nStatus: DRAFT - Budget Under Review\nTotal Allocation: RM 2,400,000\nPrincipal Investigator: Prof. Ahmad\nDepartment: FPTM\n")
        self.mkfile("/tmp/.hidden_miner_config", b"POOL=stratum+tcp://pool.monerohash.com:5555\nWALLET=49J7mRwGc7qC8wFq9zQr5PQmH2nWvKxRy3DpL6tN8sB1fUdA4gY\nTHREADS=4\n")
        self.mkfile("/proc/diskstats", b"   8       0 sda 12345 6789 987654 456789 2345 1234 87654 34567 0 12345 491234\n")

    @classmethod
    def _build_minimal(cls, os_profile_name: str = "ubuntu-22.04") -> VirtualFileSystem:
        vfs = cls(os_profile_name)
        for d in ["/", "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib64", "/media", "/mnt", "/opt", "/proc", "/root", "/run", "/sbin", "/srv", "/sys", "/tmp", "/usr", "/usr/bin", "/usr/lib", "/usr/local", "/usr/sbin", "/usr/share", "/var", "/var/log", "/var/lib", "/var/run", "/var/tmp"]:
            vfs.mkdir(d)
        vfs.mkfile("/etc/hostname", b"usas-prod-srv-01\n")
        vfs.mkfile("/etc/os-release", vfs.os_profile["os_release"])
        vfs.mkfile("/etc/passwd", b"root:x:0:0:root:/root:/bin/bash\n")
        vfs.mkfile("/etc/shadow", b"root:*:19000:0:99999:7:::\n")
        vfs.mkfile("/etc/issue", vfs.os_profile["issue"])
        vfs.mkfile("/etc/issue.net", vfs.os_profile["issue_net"])
        vfs.mkfile("/etc/motd", vfs.os_profile["motd_prefix"] + time.strftime("%a %b %d %H:%M:%S %Z %Y").encode() + b"\n")
        vfs._add_proc_stubs()
        return vfs
