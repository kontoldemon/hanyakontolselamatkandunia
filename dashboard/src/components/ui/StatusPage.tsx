"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowLeft, Home, RefreshCw } from "lucide-react";

type StatusPageProps = {
  code?: string;
  icon?: React.ReactNode;
  title: string;
  message: string;
  primaryHref?: string;
  primaryLabel?: string;
  secondaryAction?: "back" | "reload";
  onRetry?: () => void;
};

export default function StatusPage({
  code,
  icon,
  title,
  message,
  primaryHref = "/",
  primaryLabel = "Dashboard",
  secondaryAction,
  onRetry,
}: StatusPageProps) {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-surface-bg px-4 py-8 text-text-primary antialiased selection:bg-blue-500/20">
      {/* Top-left Brand Anchor */}
      <div className="absolute top-5 left-5 sm:top-6 sm:left-8 z-20">
        <Link
          href="/"
          className="group inline-flex items-center gap-2 transition opacity-85 hover:opacity-100"
        >
          <Image src="/logo.svg" alt="CloudSentinel" width={18} height={18} className="h-4.5 w-4.5" />
          <span className="font-display text-xs sm:text-sm font-bold tracking-tight text-text-primary">
            Cloud<span className="text-blue-600 dark:text-blue-400">Sentinel</span>
          </span>
        </Link>
      </div>

      {/* Ambient Lighting & Subtle Grid Texture */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden select-none">
        <div className="absolute top-1/2 left-1/2 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-500/15 blur-[130px] dark:bg-blue-500/20" />
        <div className="absolute top-1/3 left-1/2 h-[320px] w-[320px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-500/10 blur-[110px] dark:bg-indigo-500/15" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_65%_55%_at_50%_50%,#000_60%,transparent_100%)]" />
      </div>

      <div className="relative w-full max-w-[380px]">
        {/* Minimalist Frosted Glass Card */}
        <div className="overflow-hidden rounded-3xl border border-border-line/15 bg-surface-card/80 p-6 shadow-2xl backdrop-blur-xl sm:p-8">
          {/* Header */}
          <div className="mb-6 flex flex-col items-center text-center">
            {icon ? (
              <div className="mb-2 flex h-14 w-14 items-center justify-center rounded-2xl border border-rose-500/25 bg-rose-500/10 text-rose-500 shadow-lg shadow-rose-500/10">
                {icon}
              </div>
            ) : code ? (
              <div className={`font-mono font-bold tracking-tight text-text-primary ${code.length > 3 ? "text-3xl sm:text-4xl" : "text-5xl sm:text-6xl"}`}>
                {code}
              </div>
            ) : null}

            <h1 className="mt-3 font-display text-base font-semibold tracking-tight text-text-primary sm:text-lg">
              {title}
            </h1>
            <p className="mt-1.5 text-xs leading-relaxed text-text-muted">
              {message}
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Link
              href={primaryHref}
              className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-full bg-blue-600 px-4 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-500 active:scale-95 sm:flex-1"
            >
              <Home size={13} />
              <span>{primaryLabel}</span>
            </Link>

            {secondaryAction === "back" && (
              <button
                type="button"
                onClick={() => window.history.back()}
                className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-full border border-border-line/15 bg-surface-panel/50 px-4 text-xs font-semibold text-text-primary shadow-sm transition hover:bg-surface-panel active:scale-95 sm:flex-1"
              >
                <ArrowLeft size={13} />
                <span>Go Back</span>
              </button>
            )}

            {secondaryAction === "reload" && (
              <button
                type="button"
                onClick={() => (onRetry ? onRetry() : window.location.reload())}
                className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-full border border-border-line/15 bg-surface-panel/50 px-4 text-xs font-semibold text-text-primary shadow-sm transition hover:bg-surface-panel active:scale-95 sm:flex-1"
              >
                <RefreshCw size={13} />
                <span>Retry</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
