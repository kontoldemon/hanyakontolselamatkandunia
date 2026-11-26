"use client";

import { Fingerprint, PlayCircle, Radar, ShieldBan, Terminal } from "lucide-react";
import { Reveal, SectionHeader } from "./LandingPrimitives";

export default function CapabilitiesSection() {
  return (
    <section
      id="capabilities"
      className="relative flex flex-col justify-center scroll-mt-14 px-4 py-16 sm:py-20 md:min-h-dvh md:py-10 md:px-6 border-t border-border-line/[0.08]"
    >
      <div className="mx-auto w-full max-w-4xl">
        <SectionHeader
          title="What CloudSentinel Does"
          sub="Autonomous SSH deception, real-time threat fingerprinting, and automated mitigation."
        />

        <div className="mt-6 sm:mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
          {/* Card 1: Virtual Deception Sandbox */}
          <Reveal delay={30}>
            <div className="group rounded-xl sm:rounded-2xl border border-border-line/[0.12] bg-gradient-to-br from-blue-500/[0.07] via-surface-card to-surface-card px-4 py-3.5 shadow-sm transition-all duration-300 hover:border-blue-500/40 hover:shadow-md hover:shadow-blue-500/[0.06]">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="flex h-6 w-6 sm:h-7 sm:w-7 shrink-0 items-center justify-center rounded-md bg-blue-500/15 text-blue-600 dark:text-blue-400 shadow-sm shadow-blue-500/20">
                    <Terminal size={14} />
                  </div>
                  <h3 className="font-display text-xs sm:text-[13px] font-bold text-text-primary truncate">
                    Virtual SSH Deception Sandbox
                  </h3>
                </div>
                <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Port 2222
                </span>
              </div>
              <p className="mt-2 text-[11.5px] leading-relaxed text-text-muted">
                Traps unauthorized logins inside an isolated RAM sandbox. Keystrokes, commands, and payloads are captured without risking host files.
              </p>
            </div>
          </Reveal>

          {/* Card 2: HASSH Botnet Fingerprinting */}
          <Reveal delay={60}>
            <div className="group rounded-xl sm:rounded-2xl border border-border-line/[0.12] bg-gradient-to-br from-indigo-500/[0.07] via-surface-card to-surface-card px-4 py-3.5 shadow-sm transition-all duration-300 hover:border-indigo-500/40 hover:shadow-md hover:shadow-indigo-500/[0.06]">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="flex h-6 w-6 sm:h-7 sm:w-7 shrink-0 items-center justify-center rounded-md bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 shadow-sm shadow-indigo-500/20">
                    <Fingerprint size={14} />
                  </div>
                  <h3 className="font-display text-xs sm:text-[13px] font-bold text-text-primary truncate">
                    HASSH Botnet Fingerprinting
                  </h3>
                </div>
                <span className="shrink-0 inline-flex items-center rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                  Known Botnet DNA
                </span>
              </div>
              <p className="mt-2 text-[11.5px] leading-relaxed text-text-muted">
                Profiles incoming SSH sessions by cryptographic cipher handshakes, identifying automated botnets across rotating IP addresses.
              </p>
            </div>
          </Reveal>

          {/* Card 3: Keystroke DVR & Session Replay */}
          <Reveal delay={90}>
            <div className="group rounded-xl sm:rounded-2xl border border-border-line/[0.12] bg-gradient-to-br from-sky-500/[0.07] via-surface-card to-surface-card px-4 py-3.5 shadow-sm transition-all duration-300 hover:border-sky-500/40 hover:shadow-md hover:shadow-sky-500/[0.06]">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="flex h-6 w-6 sm:h-7 sm:w-7 shrink-0 items-center justify-center rounded-md bg-sky-500/15 text-sky-600 dark:text-sky-400 shadow-sm shadow-sky-500/20">
                    <PlayCircle size={14} />
                  </div>
                  <h3 className="font-display text-xs sm:text-[13px] font-bold text-text-primary truncate">
                    Keystroke DVR &amp; Session Replay
                  </h3>
                </div>
                <span className="shrink-0 inline-flex items-center rounded-full bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium text-sky-600 dark:text-sky-400 border border-sky-500/20">
                  DVR Replay
                </span>
              </div>
              <p className="mt-2 text-[11.5px] leading-relaxed text-text-muted">
                Step through recorded intruder sessions and inspect the exact bash commands, typos, and payload URLs captured in the sandbox.
              </p>
            </div>
          </Reveal>

          {/* Card 4: Autonomous SOAR Response */}
          <Reveal delay={120}>
            <div className="group rounded-xl sm:rounded-2xl border border-border-line/[0.12] bg-gradient-to-br from-rose-500/[0.07] via-surface-card to-surface-card px-4 py-3.5 shadow-sm transition-all duration-300 hover:border-rose-500/40 hover:shadow-md hover:shadow-rose-500/[0.06]">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="flex h-6 w-6 sm:h-7 sm:w-7 shrink-0 items-center justify-center rounded-md bg-rose-500/15 text-rose-600 dark:text-rose-400 shadow-sm shadow-rose-500/20">
                    <ShieldBan size={14} />
                  </div>
                  <h3 className="font-display text-xs sm:text-[13px] font-bold text-text-primary truncate">
                    Autonomous SOAR Mitigation
                  </h3>
                </div>
                <span className="shrink-0 inline-flex items-center rounded-full bg-rose-500/10 px-2 py-0.5 text-[10px] font-medium text-rose-600 dark:text-rose-400 border border-rose-500/20">
                  &lt;2ms Block
                </span>
              </div>
              <p className="mt-2 text-[11.5px] leading-relaxed text-text-muted">
                High-risk intrusion signals trigger instantaneous firewall drop rules in under 2ms, isolating hostile connection sockets automatically.
              </p>
            </div>
          </Reveal>

          {/* Card 5 (Full Width): MITRE ATT&CK & Copilot */}
          <Reveal className="sm:col-span-2" delay={150}>
            <div className="group flex flex-col justify-between gap-2.5 rounded-xl sm:rounded-2xl border border-border-line/[0.12] bg-gradient-to-r from-violet-500/[0.07] via-surface-card to-blue-500/[0.07] px-4 py-3.5 shadow-sm transition-all duration-300 hover:border-violet-500/40 hover:shadow-md hover:shadow-violet-500/[0.06] sm:flex-row sm:items-center">
              <div className="max-w-xl">
                <div className="flex items-center gap-2">
                  <div className="flex h-6 w-6 sm:h-7 sm:w-7 shrink-0 items-center justify-center rounded-md bg-violet-500/15 text-violet-600 dark:text-violet-400 shadow-sm shadow-violet-500/20">
                    <Radar size={14} />
                  </div>
                  <h3 className="font-display text-xs sm:text-[13px] font-bold text-text-primary">
                    MITRE ATT&amp;CK Mapping &amp; Copilot Insights
                  </h3>
                </div>
                <p className="mt-1.5 text-[11.5px] leading-relaxed text-text-muted">
                  Automatically classifies attacker command patterns into standard MITRE tactics with plain-language incident briefings.
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-1.5 sm:justify-end">
                <span className="rounded-full bg-violet-500/10 px-2.5 py-0.5 font-mono text-[9.5px] font-medium text-violet-600 dark:text-violet-400 border border-violet-500/20">
                  T1082 Discovery
                </span>
                <span className="rounded-full bg-blue-500/10 px-2.5 py-0.5 font-mono text-[9.5px] font-medium text-blue-600 dark:text-blue-400 border border-blue-500/20">
                  T1059 Command
                </span>
                <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 font-mono text-[9.5px] font-medium text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  T1046 Scanning
                </span>
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
