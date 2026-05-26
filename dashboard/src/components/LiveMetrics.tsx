"use client";

import { useEffect, useMemo, useState } from "react";

type Summary = {
  ok: boolean;
  source: "live" | "fallback";
  metrics: {
    activeSessions: number;
    mttbMs: number;
    totalConnections: number;
    totalAuthFailures: number;
    totalCommands: number;
    totalBlocks: number;
    blockedIpsCurrent: number;
  };
};

const initialSummary: Summary = {
  ok: false,
  source: "fallback",
  metrics: {
    activeSessions: 24,
    mttbMs: 0.96,
    totalConnections: 1248,
    totalAuthFailures: 884,
    totalCommands: 312,
    totalBlocks: 138,
    blockedIpsCurrent: 18,
  },
};

const toneClass: Record<string, string> = {
  cyan: "tone-cyan",
  green: "tone-green",
  violet: "tone-violet",
  red: "tone-red",
};

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

export function LiveMetrics() {
  const [summary, setSummary] = useState<Summary>(initialSummary);

  useEffect(() => {
    let alive = true;

    async function load() {
      try {
        const response = await fetch("/api/cloudsentinel/summary", { cache: "no-store" });
        const data = await response.json();
        if (alive) {
          setSummary(data);
        }
      } catch {
        if (alive) {
          setSummary(initialSummary);
        }
      }
    }

    load();
    const timer = window.setInterval(load, 10_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  const items = useMemo(
    () => [
      { label: "Live Sessions", value: formatNumber(summary.metrics.activeSessions), tone: "cyan" },
      { label: "Median MTTB", value: `${summary.metrics.mttbMs.toFixed(2)} ms`, tone: "green" },
      { label: "Commands", value: formatNumber(summary.metrics.totalCommands), tone: "violet" },
      { label: "Blocked IPs", value: formatNumber(summary.metrics.totalBlocks), tone: "red" },
    ],
    [summary],
  );

  return (
    <section className="metrics" aria-label="Key metrics" data-source={summary.source}>
      {items.map((item) => (
        <article className={`metric ${toneClass[item.tone]}`} key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </article>
      ))}
    </section>
  );
}
