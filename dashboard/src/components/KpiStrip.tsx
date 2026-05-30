"use client";

import { Activity, ShieldAlert, Users, Network, Zap, ShieldCheck } from "lucide-react";

interface KpiStripProps {
  totalEvents: number;
  uniqueIps: number;
  totalCountries: number;
  uniqueCommands: number;
  avgRisk: number;
  blockRate: number;
}

export default function KpiStrip({ totalEvents, uniqueIps, totalCountries, uniqueCommands, avgRisk, blockRate }: KpiStripProps) {
  const safeAvgRisk = Math.min(100, Math.max(0, Number.isFinite(avgRisk) ? avgRisk : 0));
  const safeBlockRate = Math.min(100, Math.max(0, Number.isFinite(blockRate) ? blockRate : 0));

  const kpis = [
    { label: "Total Events", value: totalEvents.toLocaleString(), icon: Activity, color: "text-blue-500", bg: "bg-blue-500/10" },
    { label: "Unique IPs", value: uniqueIps.toLocaleString(), icon: Users, color: "text-purple-500", bg: "bg-purple-500/10" },
    { label: "Countries", value: totalCountries.toLocaleString(), icon: Network, color: "text-indigo-500", bg: "bg-indigo-500/10" },
    { label: "Unique Cmds", value: uniqueCommands.toLocaleString(), icon: ShieldAlert, color: "text-amber-500", bg: "bg-amber-500/10" },
    { label: "Avg Risk", value: safeAvgRisk.toFixed(1), icon: Zap, color: "text-orange-500", bg: "bg-orange-500/10" },
    { label: "Block Rate", value: `${safeBlockRate}%`, icon: ShieldCheck, color: "text-emerald-500", bg: "bg-emerald-500/10" },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 shrink-0">
      {kpis.map((kpi, i) => (
        <div key={i} className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 p-3 flex items-center gap-3 shadow-sm">
          <div className={`p-2 rounded-lg ${kpi.bg}`}>
            <kpi.icon size={16} className={kpi.color} />
          </div>
          <div>
            <div className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">{kpi.label}</div>
            <div className="text-lg font-bold text-slate-900 dark:text-white leading-tight">{kpi.value}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
