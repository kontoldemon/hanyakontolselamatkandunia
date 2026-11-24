"use client";

import Image from "next/image";
import {
  Zap,
  Sparkles,
  Cpu,
  Eye,
  ShieldAlert,
  Check,
  X,
} from "lucide-react";
import { Reveal, SectionHeader } from "./LandingPrimitives";
import { cn } from "@/lib/utils";

const COMPARISON_ROWS = [
  {
    icon: Zap,
    capability: "Incident Mitigation (SOAR)",
    cowrie: {
      badge: "Passive Logging",
      detail: "Alerts only, requires external Fail2ban",
      negative: true,
    },
    cloudsentinel: {
      badge: "Autonomous SOAR",
      detail: "Automated iptables and NSG drop rules (< 2ms)",
      highlight: true,
    },
  },
  {
    icon: Sparkles,
    capability: "Threat Intelligence & TTPs",
    cowrie: {
      badge: "JSON Event Logs",
      detail: "Flat cowrie.json with manual SIEM triage",
      negative: true,
    },
    cloudsentinel: {
      badge: "Built-in MITRE & AI",
      detail: "17 automated TTP tags and AI Copilot",
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
      detail: "Ephemeral RAM sandbox with zero disk footprint",
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
      detail: "Live 3D threat globe and web keystroke DVR",
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
      detail: "Cipher profiling plus Isolation Forest model",
      highlight: true,
    },
  },
];

export default function ComparisonSection() {
  return (
    <section
      id="comparison"
      className="relative flex flex-col justify-center scroll-mt-14 px-3.5 py-8 sm:px-4 sm:py-10 md:min-h-dvh md:py-6 md:px-6 border-t border-border-line/[0.08] bg-surface-panel/10 overflow-hidden"
    >
      {/* Background decorative ambient lighting: Monochrome (Cowrie) on left, Electric Blue (CloudSentinel) on right */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 select-none overflow-hidden">
        {/* Left: Cowrie Black & White / Monochrome aura */}
        <div className="absolute top-1/2 -translate-y-1/2 -left-12 sm:-left-20 lg:-left-24 h-48 w-48 sm:h-72 sm:w-72 lg:h-[28rem] lg:w-[28rem] rounded-full bg-slate-900/[0.04] dark:bg-white/[0.05] blur-[70px] sm:blur-[100px] lg:blur-[140px] transition-all duration-500" />
        
        {/* Right: CloudSentinel Pure Blue aura */}
        <div className="absolute top-1/2 -translate-y-1/2 -right-12 sm:-right-20 lg:-right-24 h-48 w-48 sm:h-72 sm:w-72 lg:h-[28rem] lg:w-[28rem] rounded-full bg-blue-600/[0.06] dark:bg-blue-500/[0.08] blur-[70px] sm:blur-[100px] lg:blur-[140px] transition-all duration-500" />
      </div>

      <div className="relative z-10 mx-auto w-full max-w-4xl">
        <SectionHeader
          title="CloudSentinel vs. Traditional Cowrie"
          sub="Factual technical comparison based on Cowrie honeypot documentation and CloudSentinel architecture."
        />

        {/* Minimalist Unified Comparison Matrix */}
        <Reveal delay={40} className="mt-6 sm:mt-8">
          <div className="rounded-xl border border-border-line/[0.14] bg-surface-card/90 backdrop-blur-md shadow-xs overflow-hidden">
            {/* Table Column Headers */}
            <div className="grid grid-cols-12 px-3 sm:px-4 py-2 sm:py-2.5 bg-surface-panel/40 border-b border-border-line/[0.12] text-xs font-mono items-center gap-2">
              <div className="hidden sm:block sm:col-span-4 text-text-muted font-medium text-[11px]">
                Capability
              </div>
              <div className="col-span-6 sm:col-span-4 flex items-center justify-start gap-1.5 min-w-0">
                <Image
                  src="/cowrie-logo.png"
                  alt=""
                  width={14}
                  height={14}
                  className="w-3.5 h-3.5 object-contain dark:invert shrink-0 opacity-80"
                />
                <span className="font-semibold text-slate-700 dark:text-slate-300 text-[11px] sm:text-xs shrink-0">
                  Cowrie
                </span>
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[8.5px] sm:text-[9px] bg-slate-500/10 text-slate-500 dark:text-slate-400 font-mono font-medium shrink-0">
                  Passive
                </span>
              </div>
              <div className="col-span-6 sm:col-span-4 flex items-center justify-start gap-1.5 min-w-0">
                <Image
                  src="/logo.svg"
                  alt=""
                  width={14}
                  height={14}
                  className="w-3.5 h-3.5 object-contain shrink-0"
                />
                <span className="font-semibold text-blue-600 dark:text-blue-400 text-[11px] sm:text-xs shrink-0">
                  CloudSentinel
                </span>
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[8.5px] sm:text-[9px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-mono font-medium shrink-0">
                  SOAR
                </span>
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
                      "grid grid-cols-12 px-3 sm:px-4 py-2 sm:py-2.5 text-xs transition-colors items-center gap-x-2 gap-y-1.5 sm:gap-2",
                      idx % 2 === 0 ? "bg-transparent" : "bg-surface-panel/[0.10] sm:bg-surface-panel/[0.15]"
                    )}
                  >
                    {/* Capability Title */}
                    <div className="col-span-12 sm:col-span-4 flex items-center gap-2 pr-1 sm:pr-2">
                      <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-blue-500/10 text-blue-600 dark:text-blue-400">
                        <Icon size={12} />
                      </div>
                      <span className="font-display font-medium text-[11px] sm:text-xs text-text-primary leading-tight">
                        {row.capability}
                      </span>
                    </div>

                    {/* Cowrie Spec Card on Mobile / Column on Desktop */}
                    <div className="col-span-6 sm:col-span-4 rounded-lg sm:rounded-none p-2 sm:p-0 bg-surface-panel/20 sm:bg-transparent border sm:border-0 border-border-line/[0.08] flex flex-col justify-start min-h-[58px] sm:min-h-0">
                      <div className="flex items-center gap-1.5">
                        <X size={11} className="text-slate-400 dark:text-slate-500 shrink-0" />
                        <span className="font-mono text-[10px] sm:text-[11px] font-medium text-slate-600 dark:text-slate-400 leading-snug">
                          {row.cowrie.badge}
                        </span>
                      </div>
                      <p className="text-[9.5px] sm:text-[10px] text-text-muted/75 mt-0.5 leading-snug">
                        {row.cowrie.detail}
                      </p>
                    </div>

                    {/* CloudSentinel Spec Card on Mobile / Column on Desktop */}
                    <div className="col-span-6 sm:col-span-4 rounded-lg sm:rounded-none p-2 sm:p-0 bg-blue-500/[0.05] sm:bg-transparent border sm:border-0 border-blue-500/20 flex flex-col justify-start min-h-[58px] sm:min-h-0">
                      <div className="flex items-center gap-1.5">
                        <Check size={12} className="text-emerald-500 shrink-0 font-bold" />
                        <span className="font-mono text-[10px] sm:text-[11px] font-semibold text-blue-600 dark:text-blue-400 leading-snug">
                          {row.cloudsentinel.badge}
                        </span>
                      </div>
                      <p className="text-[9.5px] sm:text-[10px] text-text-primary/80 mt-0.5 leading-snug">
                        {row.cloudsentinel.detail}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Bottom Benchmark Micro-Bar - Clean 3-Column Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-border-line/[0.10] bg-surface-panel/30 border-t border-border-line/[0.10] text-[10.5px] sm:text-[11px] font-mono">
              <div className="px-3 py-2 sm:px-3.5 sm:py-2.5 flex items-center justify-center gap-1.5 text-center">
                <span className="text-text-muted">MTTB:</span>
                <span className="font-semibold text-emerald-600 dark:text-emerald-400">{"< 2ms"}</span>
                <span className="text-text-muted/60">(vs Manual)</span>
              </div>
              <div className="px-3 py-2 sm:px-3.5 sm:py-2.5 flex items-center justify-center gap-1.5 text-center">
                <span className="text-text-muted">MITRE TTPs:</span>
                <span className="font-semibold text-blue-600 dark:text-blue-400">17 Mapped</span>
                <span className="text-text-muted/60">(vs Raw Logs)</span>
              </div>
              <div className="px-3 py-2 sm:px-3.5 sm:py-2.5 flex items-center justify-center gap-1.5 text-center">
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
