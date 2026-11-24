"use client";

import {
  Zap,
  Sparkles,
  Cpu,
  Eye,
  ShieldAlert,
  Check,
  X,
} from "lucide-react";
import { Reveal } from "./LandingPrimitives";
import { cn } from "@/lib/utils";

const COMPARISON_ROWS = [
  {
    icon: Zap,
    capability: "Incident Mitigation (SOAR)",
    cowrie: {
      badge: "Passive Logging",
      detail: "Alerts only; external Fail2ban needed",
      negative: true,
    },
    cloudsentinel: {
      badge: "Autonomous SOAR",
      detail: "Automated iptables & NSG drop rules (< 2ms)",
      highlight: true,
    },
  },
  {
    icon: Sparkles,
    capability: "Threat Intelligence & TTPs",
    cowrie: {
      badge: "JSON Event Logs",
      detail: "Flat cowrie.json; manual SIEM triage",
      negative: true,
    },
    cloudsentinel: {
      badge: "Built-in MITRE & AI",
      detail: "17 automated TTP tags & AI Copilot",
      highlight: true,
    },
  },
  {
    icon: Cpu,
    capability: "Containment & Filesystem",
    cowrie: {
      badge: "Pickle Virtual FS",
      detail: "Static fs.pickle on host disk storage",
      negative: true,
    },
    cloudsentinel: {
      badge: "In-Memory VFS",
      detail: "Ephemeral RAM sandbox; zero disk footprint",
      highlight: true,
    },
  },
  {
    icon: Eye,
    capability: "Telemetry & Operations",
    cowrie: {
      badge: "Headless CLI Daemon",
      detail: "Terminal replay via bin/playlog only",
      negative: true,
    },
    cloudsentinel: {
      badge: "Integrated War Room",
      detail: "Live 3D threat globe & web keystroke DVR",
      highlight: true,
    },
  },
  {
    icon: ShieldAlert,
    capability: "Detection & Profiling",
    cowrie: {
      badge: "Static Decoy Profiles",
      detail: "Fixed command emulation heuristics",
      negative: true,
    },
    cloudsentinel: {
      badge: "HASSH & Behavioral ML",
      detail: "Cipher profiling + Isolation Forest model",
      highlight: true,
    },
  },
];

export default function ComparisonSection() {
  return (
    <section
      id="comparison"
      className="relative flex flex-col justify-center scroll-mt-14 px-4 py-8 sm:py-10 md:min-h-dvh md:py-6 md:px-6 border-t border-border-line/[0.08] bg-surface-panel/10 overflow-hidden"
    >
      {/* Subtle ambient gradient */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 select-none overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[22rem] w-[36rem] rounded-full bg-blue-500/[0.04] blur-[120px] dark:bg-blue-600/[0.06]" />
      </div>

      <div className="relative z-10 mx-auto w-full max-w-4xl">
        {/* Compact Header */}
        <Reveal className="mx-auto max-w-2xl text-center mb-5 sm:mb-6">
          <p className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.2em] text-blue-600 dark:text-blue-400">
            Technical Architecture
          </p>
          <h2 className="mt-1 font-display text-xl sm:text-2xl font-bold tracking-tight text-text-primary">
            CloudSentinel vs. Traditional Cowrie
          </h2>
          <p className="mt-1 text-xs text-text-muted">
            Factual technical comparison based on Cowrie honeypot documentation and CloudSentinel architecture.
          </p>
        </Reveal>

        {/* Minimalist Unified Comparison Matrix */}
        <Reveal delay={40}>
          <div className="rounded-xl border border-border-line/[0.14] bg-surface-card/90 backdrop-blur-md shadow-xs overflow-hidden">
            {/* Table Column Headers */}
            <div className="grid grid-cols-12 px-4 py-2.5 bg-surface-panel/40 border-b border-border-line/[0.12] text-xs font-mono items-center">
              <div className="col-span-12 sm:col-span-4 text-text-muted font-medium text-[11px]">
                Capability
              </div>
              <div className="col-span-6 sm:col-span-4 flex items-center gap-1.5 text-text-muted">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500/60" />
                <span className="font-semibold text-slate-700 dark:text-slate-300 text-[11px]">Cowrie Honeypot</span>
                <span className="text-[9.5px] text-text-muted/70">(Passive)</span>
              </div>
              <div className="col-span-6 sm:col-span-4 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="font-bold text-blue-600 dark:text-blue-400 text-[11px]">CloudSentinel</span>
                <span className="text-[9.5px] text-emerald-600 dark:text-emerald-400 font-semibold">(SOAR)</span>
              </div>
            </div>

            {/* Matrix Rows */}
            <div className="divide-y divide-border-line/[0.08]">
              {COMPARISON_ROWS.map((row, idx) => {
                const Icon = row.icon;
                return (
                  <div
                    key={row.capability}
                    className={cn(
                      "grid grid-cols-12 px-4 py-2.5 text-xs transition-colors items-center gap-2",
                      idx % 2 === 0 ? "bg-transparent" : "bg-surface-panel/[0.15]"
                    )}
                  >
                    {/* Capability Title */}
                    <div className="col-span-12 sm:col-span-4 flex items-center gap-2 pr-2">
                      <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-blue-500/10 text-blue-600 dark:text-blue-400">
                        <Icon size={12} />
                      </div>
                      <span className="font-display font-medium text-[11px] sm:text-xs text-text-primary leading-tight">
                        {row.capability}
                      </span>
                    </div>

                    {/* Cowrie Spec */}
                    <div className="col-span-6 sm:col-span-4 pr-2 flex flex-col justify-center">
                      <div className="flex items-center gap-1.5">
                        <X size={11} className="text-slate-400 dark:text-slate-500 shrink-0" />
                        <span className="font-mono text-[10.5px] sm:text-[11px] font-medium text-slate-600 dark:text-slate-400">
                          {row.cowrie.badge}
                        </span>
                      </div>
                      <p className="text-[10px] text-text-muted/75 mt-0.5 leading-snug">
                        {row.cowrie.detail}
                      </p>
                    </div>

                    {/* CloudSentinel Spec */}
                    <div className="col-span-6 sm:col-span-4 flex flex-col justify-center">
                      <div className="flex items-center gap-1.5">
                        <Check size={12} className="text-emerald-500 shrink-0 font-bold" />
                        <span className="font-mono text-[10.5px] sm:text-[11px] font-semibold text-blue-600 dark:text-blue-400">
                          {row.cloudsentinel.badge}
                        </span>
                      </div>
                      <p className="text-[10px] text-text-primary/80 mt-0.5 leading-snug">
                        {row.cloudsentinel.detail}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Bottom Benchmark Micro-Bar - Clean 3-Column Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-border-line/[0.10] bg-surface-panel/30 border-t border-border-line/[0.10] text-[11px] font-mono">
              <div className="px-3.5 py-2.5 flex items-center justify-center gap-1.5 text-center">
                <span className="text-text-muted">MTTB:</span>
                <span className="font-semibold text-emerald-600 dark:text-emerald-400">&lt; 2ms</span>
                <span className="text-text-muted/60">(vs Manual)</span>
              </div>
              <div className="px-3.5 py-2.5 flex items-center justify-center gap-1.5 text-center">
                <span className="text-text-muted">MITRE TTPs:</span>
                <span className="font-semibold text-blue-600 dark:text-blue-400">17 Mapped</span>
                <span className="text-text-muted/60">(vs Raw Logs)</span>
              </div>
              <div className="px-3.5 py-2.5 flex items-center justify-center gap-1.5 text-center">
                <span className="text-text-muted">Operations:</span>
                <span className="font-semibold text-violet-600 dark:text-violet-400">Live War Room</span>
                <span className="text-text-muted/60">(vs CLI)</span>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
