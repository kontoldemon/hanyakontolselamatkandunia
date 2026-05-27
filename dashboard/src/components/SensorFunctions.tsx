"use client";

import { Activity, Bot, BrainCircuit, Fingerprint, Network, Shield, Terminal } from "lucide-react";
import { useSensorOperations, useLiveThreatLogs } from "@/lib/liveEvents";
import clsx from "clsx";

const functions = [
  {
    key: "sessions",
    title: "Session Capture",
    detail: "SSH login, shell input, command replay",
    icon: Terminal,
  },
  {
    key: "fingerprint",
    title: "HASSH / JA4",
    detail: "Client fingerprint and SSH identity tracking",
    icon: Fingerprint,
  },
  {
    key: "soar",
    title: "SOAR Response",
    detail: "Risk scoring, block action, allowlist guard",
    icon: Shield,
  },
  {
    key: "mitre",
    title: "MITRE Mapping",
    detail: "Technique tagging and attack-chain graph",
    icon: BrainCircuit,
  },
  {
    key: "anomaly",
    title: "Anomaly Engine",
    detail: "Command anomaly detector status",
    icon: Activity,
  },
  {
    key: "llm",
    title: "LLM Command VFS",
    detail: "API-backed terminal replies and AI summaries",
    icon: Bot,
  },
  {
    key: "observability",
    title: "Observability",
    detail: "Prometheus metrics and readiness checks",
    icon: Network,
  },
];

function valueText(value: unknown) {
  if (typeof value === "number") {
    return value.toLocaleString();
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "boolean") {
    return value ? "on" : "off";
  }
  return "0";
}

export default function SensorFunctions() {
  const operations = useSensorOperations();
  const liveLogs = useLiveThreatLogs();
  const source = operations?.source ?? "offline";
  const metrics = operations?.sensor.metrics.data ?? {};
  const sessions = operations?.sensor.sessions.data?.sessions ?? [];
  const graph = operations?.sensor.attackGraph.data;
  const anomaly = operations?.sensor.anomaly.data;
  const llm = operations?.sensor.llm.data;
  const stats = operations?.sensor.stats.data ?? {};

  const fingerprintsSeen = new Set(
    [
      ...sessions.map((session) => (session.fingerprint ?? "").trim()),
      ...liveLogs.map((log) => (log.hassh ?? "").trim()),
    ].filter(Boolean),
  );
  const identifiedCount = sessions.filter(
    (session) => (session.client ?? "").trim() && (session.client ?? "").toLowerCase() !== "unknown",
  ).length;
  const lastBlocked = [...liveLogs].find((log) => log.action === "Blocked");
  const mttbMs = Number(metrics.mttb_ms ?? stats.mttb_ms ?? 0);

  const liveValues: Record<string, unknown> = {
    sessions: sessions.length,
    fingerprint: fingerprintsSeen.size,
    soar: metrics.total_blocks,
    mitre: graph?.nodes?.length,
    anomaly: anomaly?.available,
    llm: llm?.available
      ? llm.model
      : llm?.features && typeof llm.features === "object" && "deterministic_fallback" in llm.features
        ? "fallback-on"
        : "",
    observability: operations?.sensor.readiness.ok,
  };
  const hints: Record<string, string> = {
    sessions: `${sessions.filter((item) => (item.status ?? "").toLowerCase() === "active").length} active`,
    fingerprint: `${fingerprintsSeen.size} HASSH seen / ${identifiedCount} client identified`,
    soar: lastBlocked
      ? `last action ${lastBlocked.action.toLowerCase()} ${lastBlocked.timeToBlock ?? ""}`.trim()
      : mttbMs > 0
        ? `mttb ${mttbMs.toFixed(2)} ms`
        : "no block data",
    mitre: `${graph?.edges?.length ?? 0} graph edges`,
    anomaly:
      anomaly?.available
        ? `available${typeof anomaly?.last_detected_at === "string" ? `, last ${anomaly.last_detected_at}` : ""}`
        : "not available",
    llm: llm?.available ? `model ${llm.model}` : "fallback mode",
    observability: operations?.sensor.readiness.ok ? "readiness ok" : "readiness offline",
  };
  const isLiveValue = (key: string): boolean => {
    const value = liveValues[key];
    if (source !== "live") {
      return false;
    }
    if (key === "fingerprint") {
      return fingerprintsSeen.size > 0 || identifiedCount > 0;
    }
    if (typeof value === "boolean") {
      return value;
    }
    if (typeof value === "number") {
      return value > 0;
    }
    if (typeof value === "string") {
      const normalized = value.trim().toLowerCase();
      return Boolean(normalized) && normalized !== "n/a" && normalized !== "off" && normalized !== "offline" && normalized !== "0";
    }
    return false;
  };

  return (
    <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {functions.map((item) => {
        const Icon = item.icon;
        const active = isLiveValue(item.key);
        return (
          <article
            key={item.key}
            className="bg-white dark:bg-[#0a0a0a] p-5 rounded-xl border border-slate-200 dark:border-white/5 shadow-sm"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <div
                  className={clsx(
                    "p-2 rounded-lg",
                    active
                      ? "bg-emerald-500/10 text-emerald-500"
                      : "bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-400",
                  )}
                >
                  <Icon size={20} />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white">{item.title}</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{item.detail}</p>
                </div>
              </div>
              <span
                className={clsx(
                  "text-[10px] px-2 py-1 rounded-full border font-bold uppercase",
                  active
                    ? "border-emerald-500/30 text-emerald-500 bg-emerald-500/10"
                    : "border-slate-300 text-slate-500 bg-slate-50 dark:border-white/10 dark:bg-white/5",
                )}
              >
                {active ? "live" : "offline"}
              </span>
            </div>
            <div className="mt-4 text-2xl font-bold font-mono text-slate-900 dark:text-white">
              {valueText(liveValues[item.key])}
            </div>
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              {hints[item.key] ?? ""}
            </p>
          </article>
        );
      })}
    </section>
  );
}
