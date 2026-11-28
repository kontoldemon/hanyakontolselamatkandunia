import type {
  CapturedSession,
  DashboardStats,
  SensorOperations,
  ThreatLog,
} from "@/lib/liveEvents";
import type { AgentMessage } from "@/lib/agentActions";

export type IntelligenceSnapshot = {
  totalEvents: number;
  uniqueIps: number;
  countries: number;
  uniqueCommands: number;
  avgRisk: number;
  blockRate: number;
  topAttackName: string;
  topAttackValue: number;
  mitreCount: number;
  hasshCount: number;
  topNetwork: string;
};

type IntelStatsInput = {
  uniqueIps: number;
  totalCountries: number;
  risk: { avg: number };
  soar: { blockRate: number };
  isps: Array<{ name: string; count: number }>;
  countries: Array<{ name: string; count: number }>;
};

export function computeIntelligenceSnapshot(
  liveLogs: ThreatLog[],
  sessions: CapturedSession[],
  operations: SensorOperations | null,
  stats: DashboardStats,
  intelStats: IntelStatsInput,
): IntelligenceSnapshot {
  const safeLogs = liveLogs ?? [];
  const safeSessions = sessions ?? [];
  const distributionRows = operations?.sensor?.distribution?.data ?? [];
  const topAttack = distributionRows.length > 0
    ? distributionRows.reduce((prev, current) => (Number(prev.value) > Number(current.value) ? prev : current))
    : null;

  const mitreSet = new Set<string>();
  for (const session of safeSessions) {
    for (const tech of session.mitreTechniques ?? []) {
      if (tech) mitreSet.add(tech);
    }
  }
  for (const log of safeLogs) {
    for (const tech of log.mitreTechniques ?? []) {
      if (tech) mitreSet.add(tech);
    }
  }

  const hasshSet = new Set<string>();
  for (const session of safeSessions) {
    const fp = (session.fingerprint ?? "").trim();
    if (fp) hasshSet.add(fp);
  }
  for (const log of safeLogs) {
    const fp = (log.hassh ?? "").trim();
    if (fp) hasshSet.add(fp);
  }

  const commandSet = new Set<string>();
  for (const session of safeSessions) {
    for (const cmd of session.input ?? []) {
      const trimmed = cmd.trim();
      if (trimmed && !trimmed.startsWith("cloudsentinel.") && !trimmed.includes("[redacted]")) {
        commandSet.add(trimmed);
      }
    }
  }
  for (const log of safeLogs) {
    const payload = (log.payload ?? "").trim();
    if (log.role === "attacker" && payload && !payload.startsWith("cloudsentinel.") && !payload.includes("[redacted]")) {
      commandSet.add(payload);
    }
  }

  const totalEvents = Number(stats.totalEvents ?? safeLogs.length) || 0;
  const uniqueIps = Number(stats.uniqueIps ?? intelStats.uniqueIps) || 0;
  const countries = Number(stats.uniqueCountries ?? intelStats.totalCountries) || 0;
  const avgRisk = Number.isFinite(Number(stats.avgRisk)) ? Number(stats.avgRisk) : intelStats.risk.avg;
  const blockRate = Number.isFinite(Number(stats.blockRate)) ? Number(stats.blockRate) : intelStats.soar.blockRate;
  const topNetwork = intelStats.isps[0]?.name ?? "Unknown";

  return {
    totalEvents,
    uniqueIps,
    countries,
    uniqueCommands: commandSet.size,
    avgRisk: Number(avgRisk.toFixed(1)),
    blockRate: Number(blockRate.toFixed(1)),
    topAttackName: topAttack?.name ?? "Unknown",
    topAttackValue: Number(topAttack?.value ?? 0),
    mitreCount: mitreSet.size,
    hasshCount: hasshSet.size,
    topNetwork,
  };
}

export function buildIntelligenceFactsJson(
  intelStats: IntelStatsInput,
  sessions: CapturedSession[],
  liveLogs: ThreatLog[],
  intelligenceSnapshot: IntelligenceSnapshot,
): string {
  const topCountries = (intelStats.countries ?? [])
    .slice(0, 10)
    .map((item) => ({ name: item.name, count: item.count }));
  const topNetworks = (intelStats.isps ?? [])
    .slice(0, 10)
    .map((item) => ({ name: item.name, count: item.count }));

  const mitreCountMap = new Map<string, number>();
  for (const session of sessions) {
    for (const ttp of session.mitreTechniques ?? []) {
      if (!ttp) continue;
      mitreCountMap.set(ttp, (mitreCountMap.get(ttp) ?? 0) + Math.max(1, session.sessionCount ?? 1));
    }
  }
  for (const log of liveLogs) {
    for (const ttp of log.mitreTechniques ?? []) {
      if (!ttp) continue;
      mitreCountMap.set(ttp, (mitreCountMap.get(ttp) ?? 0) + 1);
    }
  }
  const mitreTop = [...mitreCountMap.entries()]
    .map(([id, count]) => ({ id, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 12);

  const hasshCountMap = new Map<string, number>();
  for (const session of sessions) {
    const hash = (session.fingerprint ?? "").trim();
    if (!hash) continue;
    hasshCountMap.set(hash, (hasshCountMap.get(hash) ?? 0) + Math.max(1, session.sessionCount ?? 1));
  }
  for (const log of liveLogs) {
    const hash = (log.hassh ?? "").trim();
    if (!hash) continue;
    hasshCountMap.set(hash, (hasshCountMap.get(hash) ?? 0) + 1);
  }
  const hasshTop = [...hasshCountMap.entries()]
    .map(([hash, count]) => ({ hash, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  const commandCountMap = new Map<string, number>();
  const addCommand = (raw: string) => {
    const cmd = raw.trim();
    if (!cmd || cmd.startsWith("cloudsentinel.") || cmd.includes("[redacted]")) return;
    commandCountMap.set(cmd, (commandCountMap.get(cmd) ?? 0) + 1);
  };
  for (const session of sessions) {
    for (const cmd of session.input ?? []) addCommand(cmd);
  }
  for (const log of liveLogs) {
    if (log.role === "attacker") addCommand(log.payload ?? "");
  }
  const topCommands = [...commandCountMap.entries()]
    .map(([command, count]) => ({ command, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 12);

  const passwordCounts = new Map<string, number>();
  for (const log of liveLogs) {
    const payload = String(log.payload || "").trim();
    if (!payload.toLowerCase().startsWith("[auth]")) continue;
    const match = payload.match(/\/\s*([^\s]+)\s*(?:attempt\s+\d+)?$/i);
    const value = match?.[1]?.trim();
    if (!value || value.toLowerCase() === "unknown") continue;
    passwordCounts.set(value, (passwordCounts.get(value) ?? 0) + 1);
  }
  const topPasswords = [...passwordCounts.entries()]
    .map(([password, count]) => ({ password, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 15);

  return JSON.stringify({
    window: "All time (dashboard default)",
    kpi: intelligenceSnapshot,
    topCountries,
    topNetworks,
    mitreTop,
    hasshTop,
    topCommands,
    topPasswords,
  });
}

export function buildAgentPromptContext(params: {
  pathname: string;
  stats: DashboardStats;
  sessions: CapturedSession[];
  activeIpCount: number;
  topIps: string;
  focusedSessionContext: string;
  intelligenceSnapshot: IntelligenceSnapshot;
  intelligenceFactsJson: string;
  messages: AgentMessage[];
  userMsg: string;
}): string {
  const {
    pathname,
    stats,
    sessions,
    activeIpCount,
    topIps,
    focusedSessionContext,
    intelligenceSnapshot,
    intelligenceFactsJson,
    messages,
    userMsg,
  } = params;

  const recentHistory = [...messages, { role: "user", content: userMsg } as AgentMessage]
    .slice(-6)
    .map((m) => `${m.role === "user" ? "User" : "AI"}: ${m.content}`)
    .join("\n");

  let longestSessionIp = "None";
  let longestSessionSeconds = 0;
  if (sessions.length > 0) {
    const sorted = [...sessions].sort((a, b) => {
      const durA = (a.lastSeenEpochMs || 0) - (a.firstSeenEpochMs || 0);
      const durB = (b.lastSeenEpochMs || 0) - (b.firstSeenEpochMs || 0);
      return durB - durA;
    });
    longestSessionIp = sorted[0].ip;
    longestSessionSeconds = Math.round(((sorted[0].lastSeenEpochMs || 0) - (sorted[0].firstSeenEpochMs || 0)) / 1000);
  }

  return `
Current Page: ${pathname}
Total Active Connections: ${stats.activeSessions}
Total Captured IPs: ${sessions.length} (Live: ${activeIpCount})
Total Events: ${stats.totalEvents ?? 0}
Unique Attacker IPs: ${stats.uniqueIps ?? 0}
MTTB: ${stats.mttb}
Top IPs: ${topIps}${focusedSessionContext}

Advanced Intelligence Summary:
- Most frequent (highest) attack type: ${intelligenceSnapshot.topAttackName} (${intelligenceSnapshot.topAttackValue} hits)
- Longest event/session alive: IP ${longestSessionIp} lasting ${longestSessionSeconds} seconds.
- Average Risk Score: ${intelligenceSnapshot.avgRisk}/100
- Unique Countries Targeted: ${intelligenceSnapshot.countries}
- Top ISP/Network Attacking: ${intelligenceSnapshot.topNetwork}
- SOAR Block Rate: ${intelligenceSnapshot.blockRate}%

Intelligence Dashboard Snapshot (authoritative dashboard telemetry):
- Total Events: ${intelligenceSnapshot.totalEvents}
- Unique IPs: ${intelligenceSnapshot.uniqueIps}
- MITRE Techniques Mapped: ${intelligenceSnapshot.mitreCount}
- HASSH Signatures: ${intelligenceSnapshot.hasshCount}
- Unique Commands: ${intelligenceSnapshot.uniqueCommands}

${recentHistory ? `\nRECENT CONVERSATION HISTORY:\n${recentHistory}\n` : ""}

SYSTEM INSTRUCTIONS:
You are CloudSentinel AI, an autonomous cybersecurity agent that FULLY CONTROLS the dashboard.
You can navigate pages, click buttons, change dropdowns, set filters, search, and block IPs.

STRICT DATA INTEGRITY RULES:
1. NEVER invent or estimate telemetry values.
2. If user asks summary/analytics, use ONLY values from INTELLIGENCE_FACTS_JSON below.
3. If a requested field is missing in INTELLIGENCE_FACTS_JSON, say "Not available in current telemetry snapshot".
4. Do NOT mention any number not present in this prompt context.
5. Keep the same telemetry window as provided.

PERSONALITY RULES:
1. For casual greetings (hi, hello, hey, what's up, etc), respond warmly and briefly. Ask how you can help with the honeypot monitoring. Do NOT suggest any actions or include any ACTION markers for greetings.
2. For questions about specific IPs, attackers, or threats, always reference the focused session context above if available.
3. Be conversational and human. Avoid robotic or overly technical responses unless the user asks for technical detail.
4. Never generate ACTION markers unless the user is clearly requesting an action (navigate, block, export, change settings, etc).

RESPONSE RULES:
1. Provide a concise technical explanation first (2-3 sentences max).
2. Append action markers ONLY for actionable requests. You may include MULTIPLE markers.
3. Before each marker, write a brief sentence like "I can do that for you" or "Let me change that".
4. Do NOT explain markers. Use them naturally. Be direct. No filler.
5. If you need to provide a lengthy explanation or analysis (e.g. explaining what an attacker did based on telemetry), wrap ONLY that detailed explanation in <post_action_explanation> ... </post_action_explanation> at the very end of your response. The user will only see this analysis AFTER they approve your actions.

NAVIGATION MARKERS:
[ACTION:navigate_session:IP] - View attacker session details
[ACTION:navigate_page:PATH] - Go to page (/dashboard = War Room, /sessions, /intelligence, /settings)
[ACTION:show_threat_map:] - Focus the global threat map
[ACTION:block_ip:IP] - Block an IP at the sensor firewall
[ACTION:export_data:] - Export sensor JSON data
[ACTION:toggle_exposure:] - Toggle honeypot exposure on/off

UI CONTROL MARKERS (for controlling dropdowns, search, filters, toggles):
[ACTION:ui_command:sessions.search=VALUE] - Set sessions search query
[ACTION:ui_command:sessions.filter=VALUE] - Filter sessions (all or active)
[ACTION:ui_command:settings.deception_level=VALUE] - Set deception level (full, restricted, listener)
[ACTION:ui_command:settings.hassh_action=VALUE] - Set HASSH action (drop, monitor)
[ACTION:ui_command:settings.hassh_threshold=VALUE] - Set HASSH confidence threshold (0-100)
[ACTION:ui_command:settings.soar_trigger=VALUE] - Set SOAR trigger (risk, mitre, auth_spike, any_input)
[ACTION:ui_command:settings.soar_execution=VALUE] - Set SOAR execution path (eventgrid, host)
[ACTION:ui_command:settings.fake_keys=VALUE] - Toggle fake AWS keys (true/false)
[ACTION:ui_command:intel.sort=VALUE] - Sort commands (most or least)
[ACTION:ui_command:intel.search=VALUE] - Search attacker commands
[ACTION:ui_command:replay.fullscreen=toggle] - Toggle terminal replay fullscreen
[ACTION:ui_command:replay.mode=VALUE] - Set replay filter (attacker or both)
[ACTION:ui_command:replay.copy=trigger] - Copy terminal replay to clipboard
[ACTION:ui_command:socket.fullscreen=toggle] - Toggle socket telemetry fullscreen

GLOBAL CONTROLS (work from any page):
[ACTION:ui_command:sidebar.toggle=VALUE] - Collapse or expand sidebar (collapse, expand, or toggle)
[ACTION:ui_command:sidebar.theme=VALUE] - Switch theme (dark, light, or toggle)

INTELLIGENCE_FACTS_JSON:
${intelligenceFactsJson}
  `.trim();
}
