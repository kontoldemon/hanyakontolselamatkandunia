"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowRight, ChevronDown, Lock } from "lucide-react";
import { SectionHeader, TypewriterText, scrollToId } from "./LandingPrimitives";
import { FAQS, HERO_TYPEWRITER_PHRASES, STEPS } from "./landingContent";

export function HeroSection() {
  return (
    <section
      id="top"
      className="relative flex min-h-dvh flex-col items-center justify-center overflow-hidden px-4 py-12 md:px-6"
    >
      {/* Ambient Spotted Mesh Gradient Glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 overflow-hidden select-none"
      >
        {/* Spot 1: Top-left / center blue spot */}
        <div className="animate-orb-drift-1 absolute -top-24 -left-16 h-[28rem] w-[28rem] rounded-full bg-blue-600/15 blur-[120px] dark:bg-blue-500/20" />

        {/* Spot 2: Center-right indigo spot */}
        <div className="animate-orb-drift-2 absolute top-1/4 -right-16 h-[30rem] w-[30rem] rounded-full bg-indigo-600/15 blur-[130px] dark:bg-indigo-500/20" />

        {/* Spot 3: Core centered violet spot */}
        <div className="animate-orb-drift-3 absolute top-1/3 left-1/2 -translate-x-1/2 h-[22rem] w-[22rem] rounded-full bg-violet-600/10 blur-[110px] dark:bg-violet-500/15" />

        {/* Spot 4: Bottom sky accent spot */}
        <div className="animate-orb-drift-4 absolute -bottom-20 left-1/3 h-[24rem] w-[32rem] rounded-full bg-sky-500/10 blur-[120px] dark:bg-sky-400/15" />
      </div>

      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_70%_55%_at_50%_40%,#000_50%,transparent_100%)]" />
      </div>

      <div className="relative z-10 mx-auto w-full max-w-3xl text-center">
        <h1 className="animate-fade-up font-display text-[clamp(1.75rem,4.2vw,2.75rem)] font-bold leading-[1.18] tracking-tight text-text-primary">
          Catch Intruders.
          <br />
          <span className="text-blue-600 dark:text-blue-400">
            <TypewriterText words={HERO_TYPEWRITER_PHRASES} />
          </span>
        </h1>

        <p
          className="animate-fade-up mx-auto mt-4 max-w-2xl text-balance text-xs leading-relaxed text-text-muted sm:text-base px-2 sm:px-0"
          style={{ animationDelay: "0.10s" }}
        >
          CloudSentinel spots unauthorized logins, tests attacker intent safely in a sandbox,
          and stops threats automatically in seconds before damage can occur.
        </p>

        <div
          className="animate-fade-up mt-6 flex flex-row items-center justify-center gap-2 sm:gap-3"
          style={{ animationDelay: "0.18s" }}
        >
          <Link
            href="/signin"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-full border border-transparent bg-blue-600 px-5 sm:px-6 text-xs sm:text-sm font-semibold text-white shadow-sm transition hover:bg-blue-500 active:scale-95 box-border"
          >
            <span>Enter War Room</span>
            <ArrowRight size={14} />
          </Link>
          <button
            type="button"
            onClick={() => scrollToId("how-it-works")}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-full border border-border-line/20 bg-surface-card px-5 sm:px-6 text-xs sm:text-sm font-semibold text-text-primary shadow-sm transition hover:bg-surface-panel hover:border-border-line/30 active:scale-95 box-border"
          >
            <span>How It Works</span>
          </button>
        </div>
      </div>
    </section>
  );
}

export function HowItWorksSection() {
  const stepStyles = [
    {
      card: "bg-gradient-to-br from-blue-500/[0.08] via-surface-card to-surface-card hover:border-blue-500/40 hover:shadow-md hover:shadow-blue-500/[0.06]",
      iconBg: "bg-blue-500/15 text-blue-600 dark:text-blue-400 shadow-sm shadow-blue-500/20",
      stepBadge: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20",
    },
    {
      card: "bg-gradient-to-br from-violet-500/[0.08] via-surface-card to-surface-card hover:border-violet-500/40 hover:shadow-md hover:shadow-violet-500/[0.06]",
      iconBg: "bg-violet-500/15 text-violet-600 dark:text-violet-400 shadow-sm shadow-violet-500/20",
      stepBadge: "bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-500/20",
    },
    {
      card: "bg-gradient-to-br from-rose-500/[0.08] via-surface-card to-surface-card hover:border-rose-500/40 hover:shadow-md hover:shadow-rose-500/[0.06]",
      iconBg: "bg-rose-500/15 text-rose-600 dark:text-rose-400 shadow-sm shadow-rose-500/20",
      stepBadge: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20",
    },
  ];

  return (
    <section
      id="how-it-works"
      className="relative flex flex-col justify-center overflow-hidden border-y border-border-line/[0.08] bg-surface-panel/20 px-4 py-16 sm:py-20 md:min-h-dvh md:py-10 md:px-6"
    >
      {/* Atmospheric Ambient Glows & Grid */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden select-none">
        <div className="absolute top-1/4 -right-16 h-[26rem] w-[26rem] rounded-full bg-rose-500/[0.06] blur-[130px] dark:bg-rose-600/[0.09]" />
        <div className="absolute bottom-1/4 -left-16 h-[26rem] w-[26rem] rounded-full bg-blue-500/[0.06] blur-[130px] dark:bg-blue-600/[0.09]" />
        <div className="absolute inset-0 bg-[radial-gradient(#80808014_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_75%_65%_at_50%_50%,#000_60%,transparent_100%)]" />
      </div>

      <div className="relative z-10 mx-auto w-full max-w-4xl">
        <SectionHeader
          title="How It Works"
          sub="From intrusion to containment in three simple steps."
        />

        <div className="mt-6 sm:mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3 sm:gap-4">
          {STEPS.map((s, idx) => {
            const Icon = s.icon;
            const style = stepStyles[idx % stepStyles.length];
            return (
              <div
                key={s.step}
                className={`flex flex-col justify-between rounded-xl sm:rounded-2xl border border-border-line/[0.12] p-4.5 sm:p-5 shadow-sm transition-all duration-300 ${style.card}`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <div className={`flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-lg ${style.iconBg}`}>
                      <Icon size={16} />
                    </div>
                    <span className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold ${style.stepBadge}`}>
                      {s.step}
                    </span>
                  </div>
                  <h3 className="mt-3 font-display text-xs sm:text-sm font-bold text-text-primary">
                    {s.title}
                  </h3>
                  <p className="mt-1.5 text-[11.5px] leading-relaxed text-text-muted">
                    {s.desc}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function FaqSection({
  openFaqIndex,
  onToggleFaq,
}: {
  openFaqIndex: number | null;
  onToggleFaq: (idx: number) => void;
}) {
  return (
    <section
      id="faq"
      className="relative scroll-mt-14 mx-auto max-w-3xl px-4 py-16 sm:py-24 md:px-6 overflow-hidden"
    >
      {/* Atmospheric Ambient Glow */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden select-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[28rem] w-[28rem] rounded-full bg-indigo-500/[0.05] blur-[140px] dark:bg-indigo-600/[0.08]" />
      </div>

      <div className="relative z-10">
        <SectionHeader
          title="Frequently Asked Questions"
          sub="Learn more about how the honeypot, dashboard, and AI copilot work together."
        />

        <div className="mt-6 sm:mt-8 flex flex-col gap-2">
          {FAQS.map((item, idx) => {
            const isOpen = openFaqIndex === idx;
            return (
              <div
                key={idx}
                className={`rounded-2xl border transition-all duration-200 ${
                  isOpen
                    ? "border-blue-500/40 bg-gradient-to-r from-blue-500/[0.06] via-surface-card to-surface-card shadow-sm"
                    : "border-border-line/[0.08] bg-surface-card hover:border-border-line/20"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onToggleFaq(idx)}
                  aria-expanded={isOpen}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left focus-visible:outline-none"
                >
                  <span className="font-display text-xs font-medium text-text-primary sm:text-sm">
                    {item.q}
                  </span>
                  <ChevronDown
                    size={15}
                    className={`shrink-0 text-text-muted transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                      isOpen ? "rotate-180 text-blue-600 dark:text-blue-400" : ""
                    }`}
                  />
                </button>
                <div
                  className={`grid transition-[grid-template-rows,opacity] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                    isOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
                  }`}
                >
                  <div className="overflow-hidden">
                    <p className="px-4 pb-3.5 text-xs leading-relaxed text-text-muted sm:text-sm">
                      {item.a}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function CtaSection() {
  return (
    <section className="relative px-4 py-16 sm:py-20 md:px-6 overflow-hidden">
      <div className="relative mx-auto max-w-3xl">
        {/* Radiant Ambient Glow Behind Card */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -inset-1 rounded-3xl bg-gradient-to-r from-blue-600/25 via-indigo-600/20 to-violet-600/25 blur-2xl opacity-70"
        />

        <div className="relative rounded-3xl border border-blue-500/30 bg-gradient-to-b from-blue-500/[0.09] via-surface-card to-surface-card p-6 text-center shadow-xl shadow-blue-500/[0.05] backdrop-blur-xl sm:p-10">
          <h2 className="font-display text-xl font-bold tracking-tight text-text-primary sm:text-2xl">
            Ready to explore live threat defense?
          </h2>
          <p className="mx-auto mt-2 max-w-md text-xs leading-relaxed text-text-muted">
            Access the War Room dashboard to view real-time connection attempts, replay attacker sessions,
            and interact with the AI security copilot.
          </p>
          <div className="mt-5 flex justify-center">
            <Link
              href="/signin"
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 px-6 text-xs font-semibold text-white shadow-md shadow-blue-500/25 transition hover:from-blue-500 hover:to-indigo-500 active:scale-95"
            >
              <Lock size={12} />
              <span>Launch War Room</span>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

export function LandingFooter() {
  return (
    <footer className="border-t border-border-line/[0.08] bg-surface-panel/30 py-6 text-center text-xs text-text-muted">
      <div className="mx-auto flex max-w-4xl items-center justify-center gap-2 px-4 md:px-6">
        <Image src="/logo.svg" alt="CloudSentinel" width={16} height={16} className="h-4 w-4" />
        <span className="font-display font-semibold text-text-primary">CloudSentinel</span>
        <span>&copy; {new Date().getFullYear()}</span>
      </div>
    </footer>
  );
}
