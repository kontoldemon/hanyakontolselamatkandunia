"use client";

import { Activity, Globe } from "lucide-react";
import { useMemo } from "react";
import ThreatMap from "@/components/war-room/ThreatMap";
import AttackLog from "@/components/war-room/AttackLog";
import { useWarRoomDashboardState } from "@/components/war-room/useWarRoomDashboardState";

export default function Dashboard() {
  const {
    selectedRegion,
    setSelectedRegion,
    displayConnections,
    stats,
    combinedLogs,
    underAttack,
    mappedMitreCount,
  } = useWarRoomDashboardState();

  const uniqueIpsCount = useMemo(() => new Set(combinedLogs.map((l) => l.ip)).size, [combinedLogs]);

  const topCountry = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const log of combinedLogs) {
      const c = log.countryName || log.country;
      if (c && c !== "Unknown") {
        counts[c] = (counts[c] || 0) + 1;
      }
    }
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return sorted.length > 0 ? { country: sorted[0][0], count: sorted[0][1] } : null;
  }, [combinedLogs]);

  return (
    <div className="flex flex-col gap-4 lg:h-full">
      <div className="flex items-center justify-between shrink-0">
        <div className="flex bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/5 rounded-lg shadow-sm text-xs overflow-x-auto w-full sm:w-auto scrollbar-hide">
          <div className="px-3 py-1.5 border-r border-slate-200 dark:border-white/5 shrink-0">
            <span className="text-slate-500 text-[11px] mr-2">Connections</span>
            <span className="font-mono font-semibold text-slate-900 dark:text-white">{displayConnections.toLocaleString()}</span>
          </div>
          <div className="px-3 py-1.5 border-r border-slate-200 dark:border-white/5 shrink-0">
            <span className="text-slate-500 text-[11px] mr-2">MTTB</span>
            <span className="font-mono font-semibold text-slate-900 dark:text-white">{stats.mttb}</span>
          </div>
          <div className="px-3 py-1.5 border-r border-slate-200 dark:border-white/5 shrink-0">
            <span className="text-slate-500 text-[11px] mr-2">MITRE TTPs</span>
            <span className="font-mono font-semibold text-slate-900 dark:text-white">{mappedMitreCount}</span>
          </div>
          {topCountry && (
            <div className="px-3 py-1.5 border-r border-slate-200 dark:border-white/5 flex items-center shrink-0">
              <span className="text-slate-500 text-[11px] mr-2">Top Origin</span>
              <span className="font-mono font-semibold text-rose-600 dark:text-rose-400">
                {topCountry.country} ({topCountry.count})
              </span>
            </div>
          )}
          <div className="px-3 py-1.5 shrink-0">
            <span className="text-slate-500 text-[11px] mr-2">Uptime</span>
            <span className="font-mono font-semibold text-slate-900 dark:text-white">{stats.systemUptime}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">
        <div className="lg:col-span-2 flex flex-col bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm overflow-hidden min-h-[400px] lg:min-h-0">
          <div className="flex justify-between items-center px-4 py-3 border-b border-slate-200 dark:border-white/5 shrink-0 bg-slate-50/50 dark:bg-white/[0.02]">
            <h3 className="font-display font-semibold text-[13px] tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
              <Globe size={15} className="text-blue-500" />
              Global Threat Map
            </h3>
            <div className="flex gap-3">
              <span className="flex items-center gap-1.5 text-[11px] text-slate-500 font-medium"><span className="w-1.5 h-1.5 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.8)]"></span>Auth Fail</span>
              <span className="flex items-center gap-1.5 text-[11px] text-slate-500 font-medium"><span className="w-1.5 h-1.5 rounded-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.8)]"></span>Command</span>
            </div>
          </div>
          <div className="flex-1 min-h-0 relative flex flex-col">
            <ThreatMap
              onRegionClick={setSelectedRegion}
              selectedRegion={selectedRegion}
              underAttack={underAttack}
              threatLogs={combinedLogs}
            />
          </div>
        </div>

        <div className="lg:col-span-1 flex flex-col bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm overflow-hidden min-h-[500px] lg:min-h-0">
          <div className="px-4 py-3 border-b border-slate-200 dark:border-white/5 shrink-0 bg-slate-50/50 dark:bg-white/[0.02]">
            <div className="flex items-center gap-2">
              <h3 className="font-display font-semibold text-[13px] tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                <Activity size={15} className="text-emerald-500" />
                Live Activity
              </h3>
              <span className="text-[10px] font-mono font-medium px-1.5 py-0.5 rounded bg-slate-200/60 dark:bg-white/[0.06] text-slate-600 dark:text-slate-400">
                {uniqueIpsCount} IPs
              </span>
            </div>
          </div>
          <div className="flex-1 min-h-0 overflow-hidden p-2">
            <AttackLog selectedRegion={selectedRegion} threatLogs={combinedLogs} />
          </div>
        </div>
      </div>
    </div>
  );
}
