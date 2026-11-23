export type AgentActionType =
  | "navigate_session"
  | "navigate_page"
  | "show_threat_map"
  | "block_ip"
  | "export_data"
  | "toggle_exposure"
  | "ui_command";

const VALID_ACTION_TYPES: ReadonlySet<AgentActionType> = new Set<AgentActionType>([
  "navigate_session",
  "navigate_page",
  "show_threat_map",
  "block_ip",
  "export_data",
  "toggle_exposure",
  "ui_command",
]);

export interface AgentAction {
  type: AgentActionType;
  label: string;
  description: string;
  params: Record<string, string>;
}

export interface AgentMessage {
  role: "user" | "ai";
  content: string;
  postActionContent?: string;
  actions?: AgentAction[];
  actionState?: "pending" | "approved" | "executing" | "done" | "denied";
}

export const UI_TARGETS: Record<string, { page: string; label: string }> = {
  "sessions.search":          { page: "/sessions", label: "Sessions search" },
  "sessions.filter":          { page: "/sessions", label: "Sessions filter" },
  "sessions.select":          { page: "/sessions", label: "Select session" },
  "intel.sort":               { page: "/intelligence", label: "Command sort order" },
  "intel.search":             { page: "/intelligence", label: "Command search" },
  "intel.page":               { page: "/intelligence", label: "Command page" },
  "settings.deception_level": { page: "/settings", label: "Deception level" },
  "settings.hassh_action":    { page: "/settings", label: "HASSH action" },
  "settings.hassh_threshold": { page: "/settings", label: "HASSH confidence threshold" },
  "settings.soar_trigger":    { page: "/settings", label: "SOAR trigger condition" },
  "settings.soar_execution":  { page: "/settings", label: "SOAR execution path" },
  "settings.fake_keys":       { page: "/settings", label: "Fake AWS keys injection" },
  "socket.fullscreen":        { page: "/settings", label: "Socket telemetry fullscreen" },
  "replay.fullscreen":        { page: "/sessions", label: "Replay fullscreen" },
  "replay.mode":              { page: "/sessions", label: "Replay filter mode" },
  "replay.copy":              { page: "/sessions", label: "Copy replay" },
  "sidebar.toggle":           { page: "*", label: "Sidebar collapse/expand" },
  "sidebar.theme":            { page: "*", label: "Theme mode" },
};

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
      const names: Record<string, string> = {
        "/dashboard": "War Room",
        "/sessions": "Sessions",
        "/intelligence": "Intelligence",
        "/settings": "Settings",
      };
      return { label: `Go to ${names[param] ?? capitalize(param)}`, description: `Navigate to the ${names[param] ?? param} page` };
    }
    case "show_threat_map":
      return { label: "Show Threat Map", description: "Navigate to War Room and focus the global map" };
    case "export_data":
      return { label: "Export Sensor Data", description: "Download the full sensor JSON payload" };
    case "toggle_exposure":
      return { label: "Toggle Honeypot Exposure", description: "Pause or resume public honeypot traffic" };
    case "ui_command": {
      const [target, value] = param.split("=");
      const meta = UI_TARGETS[target];
      const friendlyLabel = meta?.label ?? target;
      return { label: `Set ${friendlyLabel}`, description: `Change ${friendlyLabel} to "${value ?? "toggle"}"` };
    }
    default:
      return { label: String(type), description: "" };
  }
}

export function parseActionsFromResponse(aiText: string): { cleanText: string; postActionContent?: string; actions: AgentAction[] } {
  const actions: AgentAction[] = [];
  let postActionContent: string | undefined;

  const match = aiText.match(/<post_action_explanation>([\s\S]*?)<\/post_action_explanation>/i);
  let processText = aiText;
  if (match) {
    postActionContent = match[1].trim();
    processText = aiText.replace(match[0], "").trim();
  }

  const cleanText = processText.replace(MARKER_RE, (_, rawType: string, rawParam: string) => {
    const type = rawType as AgentActionType;
    if (!VALID_ACTION_TYPES.has(type)) {
      return "";
    }
    const param = (rawParam ?? "").trim();

    if (type === "ui_command") {
      const eqIndex = param.indexOf("=");
      const target = eqIndex >= 0 ? param.slice(0, eqIndex) : param;
      const value = eqIndex >= 0 ? param.slice(eqIndex + 1) : "toggle";
      const { label, description } = labelForAction(type, param);
      actions.push({ type, label, description, params: { target, value } });
    } else {
      let resolvedParam = param;
      if (type === "navigate_page" && param === "/") resolvedParam = "/dashboard";
      if (type === "navigate_page") {
        const allowed = new Set(["/dashboard", "/sessions", "/intelligence", "/settings"]);
        const normalized = resolvedParam.startsWith("/") ? resolvedParam : `/${resolvedParam}`;
        resolvedParam = allowed.has(normalized) ? normalized : "/dashboard";
      }
      const { label, description } = labelForAction(type, resolvedParam);
      actions.push({ type, label, description, params: { value: resolvedParam } });
    }
    return "";
  }).replace(/\n{3,}/g, "\n\n").trim();

  return { cleanText, postActionContent, actions };
}

export { detectIntentActions } from "./agentIntentDetector";
