"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, Crosshair, Globe, Zap } from "lucide-react";

type SummaryPayload = {
  ok?: boolean;
  status?: "live" | "offline";
  metrics?: {
    totalEvents?: number;
    uniqueCountries?: number;
    mttbMs?: number;
  };
};

function formatCompact(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0";
  return Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function StatCard({ value, label, icon, delay }: { value: string; label: string; icon: React.ReactNode; delay: string }) {
  return (
    <div className={`rounded-xl border border-white/5 bg-[#0a0a0a]/80 backdrop-blur-xl p-3 text-center shadow-lg hover:border-white/10 hover:scale-105 transition-all animate-fade-in-up ${delay}`}>
      <div className="flex justify-center mb-1">{icon}</div>
      <div className="text-lg md:text-xl font-extrabold tracking-tight text-white">{value}</div>
      <div className="text-[9px] text-slate-400 font-medium mt-0.5">{label}</div>
    </div>
  );
}

export default function LandingLiveStats() {
  const [summary, setSummary] = useState<SummaryPayload | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const res = await fetch("/api/cloudsentinel/summary", { cache: "no-store" });
        if (!res.ok) return;
        const json = (await res.json()) as SummaryPayload;
        if (!cancelled) setSummary(json);
      } catch {
        // keep fallback values
      }
    };

    void load();
    const timer = window.setInterval(() => void load(), 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const values = useMemo(() => {
    const totalEvents = Number(summary?.metrics?.totalEvents ?? 0);
    const countries = Number(summary?.metrics?.uniqueCountries ?? 0);
    const mttbMs = Number(summary?.metrics?.mttbMs ?? 0);
    const status = summary?.status === "live" ? "Live" : "Offline";
    return {
      threats: totalEvents > 0 ? formatCompact(totalEvents) : "50,000+",
      countries: countries > 0 ? `${countries}` : "190+",
      mttb: mttbMs > 0 ? `${mttbMs.toFixed(2)}ms` : "<15ms",
      status: summary ? status : "24/7",
    };
  }, [summary]);

  return (
    <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-3 pt-10 px-4 md:px-8">
      <StatCard value={values.threats} label="Threats Analyzed" icon={<Crosshair size={16} className="text-red-400" />} delay="anim-delay-100" />
      <StatCard value={values.countries} label="Countries Tracked" icon={<Globe size={16} className="text-blue-400" />} delay="anim-delay-200" />
      <StatCard value={values.mttb} label="Avg MTTB" icon={<Zap size={16} className="text-amber-400" />} delay="anim-delay-300" />
      <StatCard value={values.status} label="Active Monitoring" icon={<Activity size={16} className="text-emerald-400" />} delay="anim-delay-400" />
    </div>
  );
}

