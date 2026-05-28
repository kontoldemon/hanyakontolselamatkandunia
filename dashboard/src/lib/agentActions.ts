// ─── Agent Action Type System ────────────────────────────────────────────────

export type AgentActionType =
  // ── Navigation ──
  | "navigate_session"
  | "navigate_page"
  | "show_threat_map"
  // ── API Actions ──
  | "block_ip"
  | "export_data"
  | "toggle_exposure"
  // ── Generic UI Command (controls dropdowns, search, filters, toggles) ──
  | "ui_command";

export interface AgentAction {
  type: AgentActionType;
  label: string;
  description: string;
  params: Record<string, string>;
}

export interface AgentMessage {
  role: "user" | "ai";
  content: string;
  actions?: AgentAction[];
  actionState?: "pending" | "approved" | "executing" | "done" | "denied";
}

// ─── UI Command Target Registry ─────────────────────────────────────────────
// Maps human-readable target names to their page path for auto-navigation.

export const UI_TARGETS: Record<string, { page: string; label: string }> = {
  // Sessions page
  "sessions.search":          { page: "/sessions", label: "Sessions search" },
  "sessions.filter":          { page: "/sessions", label: "Sessions filter" },
  "sessions.select":          { page: "/sessions", label: "Select session" },
  // Intelligence page
  "intel.sort":               { page: "/intelligence", label: "Command sort order" },
  "intel.search":             { page: "/intelligence", label: "Command search" },
  "intel.page":               { page: "/intelligence", label: "Command page" },
  "intel.response_filter":    { page: "/intelligence", label: "Response mode filter" },
  // Settings page
  "settings.deception_level": { page: "/settings", label: "Deception level" },
  "settings.hassh_action":    { page: "/settings", label: "HASSH action" },
  "settings.hassh_threshold": { page: "/settings", label: "HASSH confidence threshold" },
  "settings.soar_trigger":    { page: "/settings", label: "SOAR trigger condition" },
  "settings.soar_execution":  { page: "/settings", label: "SOAR execution path" },
  "settings.fake_keys":       { page: "/settings", label: "Fake AWS keys injection" },
  "socket.fullscreen":        { page: "/settings", label: "Socket telemetry fullscreen" },
  // Terminal Replay (lives on Sessions page)
  "replay.fullscreen":        { page: "/sessions", label: "Replay fullscreen" },
  "replay.mode":              { page: "/sessions", label: "Replay filter mode" },
  "replay.copy":              { page: "/sessions", label: "Copy replay" },
  // Global (sidebar is always mounted on desktop)
  "sidebar.toggle":           { page: "*", label: "Sidebar collapse/expand" },
  "sidebar.theme":            { page: "*", label: "Theme mode" },
};

// ─── Marker Parsing ─────────────────────────────────────────────────────────
// LLM returns markers like:
//   [ACTION:navigate_session:1.2.3.4]
//   [ACTION:block_ip:1.2.3.4]
//   [ACTION:ui_command:sessions.search=1.2.3.4]

const MARKER_RE = /\[ACTION:(\w+):([^\]]*)\]/g;

function capitalize(s: string): string {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function labelForAction(type: AgentActionType, param: string): { label: string; description: string } {
  switch (type) {
    case "navigate_session":
      return { label: `View attacker ${param}`, description: "Navigate to Sessions and show full details" };
    case "block_ip":
      return { label: `Block IP ${param}`, description: "Apply iptables firewall rule at the sensor" };
    case "navigate_page": {
      const names: Record<string, string> = { "/": "War Room", "/sessions": "Sessions", "/intelligence": "Intelligence", "/settings": "Settings" };
      return { label: `Go to ${names[param] ?? capitalize(param)}`, description: `Navigate to the ${names[param] ?? param} page` };
    }
    case "show_threat_map":
      return { label: "Show Threat Map", description: "Navigate to War Room and focus the global map" };
    case "export_data":
      return { label: "Export Sensor Data", description: "Download the full sensor JSON payload" };
    case "toggle_exposure":
      return { label: "Toggle Honeypot Exposure", description: "Pause or resume public honeypot traffic" };
    case "ui_command": {
      // param is "target=value"
      const [target, value] = param.split("=");
      const meta = UI_TARGETS[target];
      const friendlyLabel = meta?.label ?? target;
      return { label: `Set ${friendlyLabel}`, description: `Change ${friendlyLabel} to "${value ?? "toggle"}"` };
    }
    default:
      return { label: String(type), description: "" };
  }
}

export function parseActionsFromResponse(aiText: string): { cleanText: string; actions: AgentAction[] } {
  const actions: AgentAction[] = [];
  const cleanText = aiText.replace(MARKER_RE, (_, rawType: string, rawParam: string) => {
    const type = rawType as AgentActionType;
    const param = (rawParam ?? "").trim();

    if (type === "ui_command") {
      const eqIndex = param.indexOf("=");
      const target = eqIndex >= 0 ? param.slice(0, eqIndex) : param;
      const value = eqIndex >= 0 ? param.slice(eqIndex + 1) : "toggle";
      const { label, description } = labelForAction(type, param);
      actions.push({ type, label, description, params: { target, value } });
    } else {
      const { label, description } = labelForAction(type, param);
      actions.push({ type, label, description, params: { value: param } });
    }
    return "";
  }).trim();
  return { cleanText, actions };
}

// ─── Fallback Intent Detection ──────────────────────────────────────────────

const IP_RE = /\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b/;

const PAGE_KEYWORDS: Record<string, string> = {
  "war room": "/",
  "dashboard": "/",
  "session": "/sessions",
  "sessions": "/sessions",
  "intelligence": "/intelligence",
  "threat intel": "/intelligence",
  "setting": "/settings",
  "settings": "/settings",
  "config": "/settings",
};

export function detectIntentActions(userMessage: string, aiResponse: string): AgentAction[] {
  const combined = `${userMessage} ${aiResponse}`.toLowerCase();
  const userLower = userMessage.toLowerCase();
  const actions: AgentAction[] = [];
  const ipMatch = userMessage.match(IP_RE) ?? aiResponse.match(IP_RE);
  const ip = ipMatch?.[1] ?? "";

  // ── Block intent ──
  const blockWords = ["block", "ban", "firewall", "stop", "blacklist", "deny"];
  if (ip && blockWords.some((w) => combined.includes(w))) {
    actions.push({
      type: "block_ip",
      label: `Block IP ${ip}`,
      description: "Apply iptables firewall rule at the sensor",
      params: { value: ip },
    });
  }

  // ── Navigate to session intent ──
  const sessionWords = ["detail", "show", "view", "look at", "investigate", "attacker", "who is", "info"];
  if (ip && sessionWords.some((w) => combined.includes(w))) {
    actions.push({
      type: "navigate_session",
      label: `View attacker ${ip}`,
      description: "Navigate to Sessions and show full details",
      params: { value: ip },
    });
  }

  // ── Navigate to page intent ──
  const navWords = ["go to", "navigate", "open", "switch to", "take me"];
  if (navWords.some((w) => combined.includes(w))) {
    for (const [keyword, path] of Object.entries(PAGE_KEYWORDS)) {
      if (combined.includes(keyword)) {
        actions.push({
          type: "navigate_page",
          label: `Go to ${capitalize(keyword)}`,
          description: `Navigate to the ${capitalize(keyword)} page`,
          params: { value: path },
        });
        break;
      }
    }
  }

  // ── Threat map intent ──
  if (["threat map", "global map", "show map"].some((w) => combined.includes(w))) {
    actions.push({ type: "show_threat_map", label: "Show Threat Map", description: "Navigate to War Room and focus the global map", params: {} });
  }

  // ── Export intent ──
  if (["export", "download", "save data", "dump"].some((w) => combined.includes(w))) {
    actions.push({ type: "export_data", label: "Export Sensor Data", description: "Download the full sensor JSON payload", params: {} });
  }

  // ── Exposure toggle intent ──
  if (["exposure", "pause honeypot", "resume honeypot", "toggle exposure"].some((w) => combined.includes(w))) {
    actions.push({ type: "toggle_exposure", label: "Toggle Honeypot Exposure", description: "Pause or resume public traffic", params: {} });
  }

  // ── Settings dropdown intents ──
  const settingsTargets: { keywords: string[]; target: string; values: Record<string, string> }[] = [
    {
      keywords: ["deception level", "deception", "vfs"],
      target: "settings.deception_level",
      values: { high: "High (Full VFS)", medium: "Medium (Restricted)", low: "Low (Port listener)" },
    },
    {
      keywords: ["hassh action", "hassh", "fingerprint action"],
      target: "settings.hassh_action",
      values: { drop: "Immediate Drop", monitor: "Allow & Monitor", tarpit: "Tarpit" },
    },
    {
      keywords: ["soar trigger", "trigger condition"],
      target: "settings.soar_trigger",
      values: { mitre: "MITRE Match (>1)", spike: "Auth Spike (>10/m)", any: "Any Input" },
    },
    {
      keywords: ["execution path", "soar execution", "lambda", "docker"],
      target: "settings.soar_execution",
      values: { warm: "Lambda (Warm)", cold: "Lambda (Cold)", docker: "Local Docker" },
    },
  ];

  for (const cfg of settingsTargets) {
    if (cfg.keywords.some((k) => combined.includes(k))) {
      // Try to detect the value from user message
      let matchedValue = "";
      for (const [hint, val] of Object.entries(cfg.values)) {
        if (userLower.includes(hint) || userLower.includes(val.toLowerCase())) {
          matchedValue = val;
          break;
        }
      }
      if (matchedValue) {
        const meta = UI_TARGETS[cfg.target];
        actions.push({
          type: "ui_command",
          label: `Set ${meta?.label ?? cfg.target}`,
          description: `Change ${meta?.label ?? cfg.target} to "${matchedValue}"`,
          params: { target: cfg.target, value: matchedValue },
        });
      }
    }
  }

  // ── Sessions filter intent ──
  if (["active only", "show active", "filter active", "active sessions"].some((w) => combined.includes(w))) {
    actions.push({ type: "ui_command", label: "Filter active sessions", description: "Show only active sessions", params: { target: "sessions.filter", value: "active" } });
  }
  if (["all sessions", "show all", "all logs"].some((w) => combined.includes(w))) {
    actions.push({ type: "ui_command", label: "Show all sessions", description: "Remove session filter", params: { target: "sessions.filter", value: "all" } });
  }

  // ── Sessions search intent ──
  if (ip && ["search", "find", "look up", "filter"].some((w) => combined.includes(w))) {
    actions.push({ type: "ui_command", label: `Search sessions for ${ip}`, description: "Set the sessions search query", params: { target: "sessions.search", value: ip } });
  }

  // ── Intelligence sort intent ──
  if (["least used", "least common", "rare command"].some((w) => combined.includes(w))) {
    actions.push({ type: "ui_command", label: "Sort: least used commands", description: "Switch to least-used command sort", params: { target: "intel.sort", value: "least" } });
  }
  if (["most used", "most common", "top command", "popular command"].some((w) => combined.includes(w))) {
    actions.push({ type: "ui_command", label: "Sort: most used commands", description: "Switch to most-used command sort", params: { target: "intel.sort", value: "most" } });
  }

  // ── Fullscreen intents ──
  if (["fullscreen replay", "expand replay", "maximize replay"].some((w) => combined.includes(w))) {
    actions.push({ type: "ui_command", label: "Toggle replay fullscreen", description: "Expand terminal replay to fullscreen", params: { target: "replay.fullscreen", value: "toggle" } });
  }
  if (["fullscreen socket", "expand socket", "maximize telemetry", "fullscreen telemetry"].some((w) => combined.includes(w))) {
    actions.push({ type: "ui_command", label: "Toggle socket fullscreen", description: "Expand socket telemetry to fullscreen", params: { target: "socket.fullscreen", value: "toggle" } });
  }

  // ── Sidebar intents ──
  if (["collapse sidebar", "hide sidebar", "minimize sidebar", "close sidebar"].some((w) => combined.includes(w))) {
    actions.push({ type: "ui_command", label: "Collapse sidebar", description: "Minimize the navigation sidebar", params: { target: "sidebar.toggle", value: "collapse" } });
  }
  if (["expand sidebar", "show sidebar", "open sidebar", "maximize sidebar"].some((w) => combined.includes(w))) {
    actions.push({ type: "ui_command", label: "Expand sidebar", description: "Expand the navigation sidebar", params: { target: "sidebar.toggle", value: "expand" } });
  }

  // ── Theme intents ──
  if (["dark mode", "dark theme", "switch to dark", "enable dark"].some((w) => combined.includes(w))) {
    actions.push({ type: "ui_command", label: "Switch to dark mode", description: "Change the dashboard theme to dark", params: { target: "sidebar.theme", value: "dark" } });
  }
  if (["light mode", "light theme", "switch to light", "enable light"].some((w) => combined.includes(w))) {
    actions.push({ type: "ui_command", label: "Switch to light mode", description: "Change the dashboard theme to light", params: { target: "sidebar.theme", value: "light" } });
  }

  // Deduplicate by type+target
  const seen = new Set<string>();
  return actions.filter((a) => {
    const key = `${a.type}:${a.params.target ?? a.params.value ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
