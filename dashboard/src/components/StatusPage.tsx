"use client";

import Link from "next/link";
import { ArrowLeft, Home, RefreshCw, ShieldAlert } from "lucide-react";

type StatusPageProps = {
  code: string;
  title: string;
  message: string;
  primaryHref?: string;
  primaryLabel?: string;
  secondaryAction?: "back" | "reload";
};

export default function StatusPage({
  code,
  title,
  message,
  primaryHref = "/",
  primaryLabel = "Dashboard",
  secondaryAction,
}: StatusPageProps) {
  return (
    <main className="fixed inset-0 z-50 flex min-h-screen items-center justify-center bg-slate-50 px-4 text-slate-900 dark:bg-[#050505] dark:text-slate-100">
      <section className="w-full max-w-md text-center">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-xl border border-slate-200 bg-white text-blue-600 shadow-sm dark:border-white/10 dark:bg-[#0a0a0a] dark:text-blue-400">
          <ShieldAlert size={28} />
        </div>
        <p className="mb-2 font-mono text-xs font-bold uppercase tracking-[0.35em] text-slate-400">
          {code}
        </p>
        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">{title}</h1>
        <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-slate-500 dark:text-slate-400">
          {message}
        </p>
        <div className="mt-7 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            href={primaryHref}
            className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white transition-colors hover:bg-blue-500 sm:w-auto"
          >
            <Home size={16} />
            {primaryLabel}
          </Link>
          {secondaryAction === "back" && (
            <Link
              href="/"
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10 sm:w-auto"
            >
              <ArrowLeft size={16} />
              Back
            </Link>
          )}
          {secondaryAction === "reload" && (
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10 sm:w-auto"
            >
              <RefreshCw size={16} />
              Retry
            </button>
          )}
        </div>
      </section>
    </main>
  );
}
