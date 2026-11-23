import {
  UI_TARGETS,
  type AgentAction,
  type AgentMessage,
} from "./agentActions";

const IP_RE = /\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b/;

const PAGE_KEYWORDS: Record<string, string> = {
  "war room": "/dashboard",
  "dashboard": "/dashboard",
  "session": "/sessions",
  "sessions": "/sessions",
  "intelligence": "/intelligence",
  "threat intel": "/intelligence",
  "setting": "/settings",
  "settings": "/settings",
  "config": "/settings",
};

function capitalize(s: string): string {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function detectIntentActions(
  userMessage: string,
  aiResponse: string,
  history: AgentMessage[] = [],
): AgentAction[] {
  const userLower = userMessage.toLowerCase();
  const actions: AgentAction[] = [];
  const ipMatch = userMessage.match(IP_RE) ?? aiResponse.match(IP_RE);
  const ip = ipMatch?.[1] ?? "";

  let lastAction: AgentAction | null = null;
  if (history && history.length > 0) {
    for (let i = history.length - 1; i >= 0; i--) {
      if (history[i].actions && history[i].actions!.length > 0) {
        lastAction = history[i].actions![0];
        break;
      }
    }
  }

  if (lastAction?.type === "ui_command" && lastAction.params.target === "sidebar.toggle") {
    const isSidebarCollapse = lastAction.params.value === "collapse";
    if (isSidebarCollapse && ["open it back", "open it again", "expand it", "show it", "bring it back", "undo", "open it", "turn it on"].some((w) => userLower.includes(w))) {
      actions.push({
        type: "ui_command",
        label: "Expand sidebar",
        description: "Expand the navigation sidebar back",
        params: { target: "sidebar.toggle", value: "expand" },
      });
    } else if (!isSidebarCollapse && ["close it", "hide it", "collapse it", "undo", "turn it off"].some((w) => userLower.includes(w))) {
      actions.push({
        type: "ui_command",
        label: "Collapse sidebar",
        description: "Minimize the navigation sidebar",
        params: { target: "sidebar.toggle", value: "collapse" },
      });
    }
  }

  const blockWords = ["block", "ban", "firewall", "stop", "blacklist", "deny"];
  if (ip && blockWords.some((w) => userLower.includes(w))) {
    actions.push({
      type: "block_ip",
      label: `Block IP ${ip}`,
      description: "Apply iptables firewall rule at the sensor",
      params: { value: ip },
    });
  }

  const sessionWords = ["detail", "show", "view", "look at", "investigate", "attacker", "who is", "info"];
  if (ip && sessionWords.some((w) => userLower.includes(w))) {
    actions.push({
      type: "navigate_session",
      label: `View attacker ${ip}`,
      description: "Navigate to Sessions and show full details",
      params: { value: ip },
    });
  }

  const navWords = ["go to", "navigate", "open", "switch to", "take me"];
  if (navWords.some((w) => userLower.includes(w))) {
    for (const [keyword, path] of Object.entries(PAGE_KEYWORDS)) {
      if (userLower.includes(keyword)) {
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

  if (["threat map", "global map", "show map"].some((w) => userLower.includes(w))) {
    actions.push({ type: "show_threat_map", label: "Show Threat Map", description: "Navigate to War Room and focus the global map", params: {} });
  }

  if (["export", "download", "save data", "dump"].some((w) => userLower.includes(w))) {
    actions.push({ type: "export_data", label: "Export Sensor Data", description: "Download the full sensor JSON payload", params: {} });
  }

  if (["exposure", "pause honeypot", "resume honeypot", "toggle exposure"].some((w) => userLower.includes(w))) {
    actions.push({ type: "toggle_exposure", label: "Toggle Honeypot Exposure", description: "Pause or resume public traffic", params: {} });
  }

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
    if (cfg.keywords.some((k) => userLower.includes(k))) {
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

  if (["active only", "show active", "filter active", "active sessions"].some((w) => userLower.includes(w))) {
    actions.push({ type: "ui_command", label: "Filter active sessions", description: "Show only active sessions", params: { target: "sessions.filter", value: "active" } });
  }
  if (["all sessions", "show all", "all logs"].some((w) => userLower.includes(w))) {
    actions.push({ type: "ui_command", label: "Show all sessions", description: "Remove session filter", params: { target: "sessions.filter", value: "all" } });
  }

  if (ip && ["search", "find", "look up", "filter"].some((w) => userLower.includes(w))) {
    actions.push({ type: "ui_command", label: `Search sessions for ${ip}`, description: "Set the sessions search query", params: { target: "sessions.search", value: ip } });
  }

  if (["least used", "least common", "rare command"].some((w) => userLower.includes(w))) {
    actions.push({ type: "ui_command", label: "Sort: least used commands", description: "Switch to least-used command sort", params: { target: "intel.sort", value: "least" } });
  }
  if (["most used", "most common", "top command", "popular command"].some((w) => userLower.includes(w))) {
    actions.push({ type: "ui_command", label: "Sort: most used commands", description: "Switch to most-used command sort", params: { target: "intel.sort", value: "most" } });
  }

  if (["fullscreen replay", "expand replay", "maximize replay"].some((w) => userLower.includes(w))) {
    actions.push({ type: "ui_command", label: "Toggle replay fullscreen", description: "Expand terminal replay to fullscreen", params: { target: "replay.fullscreen", value: "toggle" } });
  }
  if (["fullscreen socket", "expand socket", "maximize telemetry", "fullscreen telemetry"].some((w) => userLower.includes(w))) {
    actions.push({ type: "ui_command", label: "Toggle socket fullscreen", description: "Expand socket telemetry to fullscreen", params: { target: "socket.fullscreen", value: "toggle" } });
  }

  if (["collapse sidebar", "hide sidebar", "minimize sidebar", "close sidebar"].some((w) => userLower.includes(w))) {
    actions.push({ type: "ui_command", label: "Collapse sidebar", description: "Minimize the navigation sidebar", params: { target: "sidebar.toggle", value: "collapse" } });
  }
  if (["expand sidebar", "show sidebar", "open sidebar", "maximize sidebar"].some((w) => userLower.includes(w))) {
    actions.push({ type: "ui_command", label: "Expand sidebar", description: "Expand the navigation sidebar", params: { target: "sidebar.toggle", value: "expand" } });
  }

  if (["dark mode", "dark theme", "switch to dark", "enable dark"].some((w) => userLower.includes(w))) {
    actions.push({ type: "ui_command", label: "Switch to dark mode", description: "Change the dashboard theme to dark", params: { target: "sidebar.theme", value: "dark" } });
  }
  if (["light mode", "light theme", "switch to light", "enable light"].some((w) => userLower.includes(w))) {
    actions.push({ type: "ui_command", label: "Switch to light mode", description: "Change the dashboard theme to light", params: { target: "sidebar.theme", value: "light" } });
  }

  const seen = new Set<string>();
  return actions.filter((a) => {
    const key = `${a.type}:${a.params.target ?? a.params.value ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
