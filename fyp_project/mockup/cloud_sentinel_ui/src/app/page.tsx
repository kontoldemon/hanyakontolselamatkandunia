"use client";

import { Users, Activity, Globe, Zap, Target, Server } from "lucide-react";
import ThreatMap from "@/components/ThreatMap";
import AttackLog from "@/components/AttackLog";
import { useDashboardStats } from "@/lib/liveEvents";
import { useState } from "react";

export default function Dashboard() {
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const stats = useDashboardStats();

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-500 bg-clip-text text-transparent">War Room</h2>
          <p className="text-slate-600 dark:text-slate-400 text-sm">Real-time Threat Intelligence Monitor</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1 bg-red-500/10 border border-red-500/20 rounded-full">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
          </span>
          <span className="text-xs font-bold text-red-500">SYSTEM UNDER ATTACK</span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-[#0a0a0a] p-5 rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
          <div className="flex justify-between items-center">
            <div>
              <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold">Connections</p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{stats.concurrentConnections.toLocaleString()}</h3>
            </div>
            <div className="p-2 bg-blue-500/10 rounded-lg text-blue-500"><Users size={20} /></div>
          </div>
        </div>
        <div className="bg-white dark:bg-[#0a0a0a] p-5 rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
          <div className="flex justify-between items-center">
            <div>
              <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold">MTTB</p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{stats.mttb}</h3>
            </div>
            <div className="p-2 bg-purple-500/10 rounded-lg text-purple-500"><Zap size={20} /></div>
          </div>
        </div>
        <div className="bg-white dark:bg-[#0a0a0a] p-5 rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
          <div className="flex justify-between items-center">
            <div>
              <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold">MITRE TTPs</p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{stats.mitreCoverage} mapped</h3>
            </div>
            <div className="p-2 bg-red-500/10 rounded-lg text-red-500"><Target size={20} /></div>
          </div>
        </div>
        <div className="bg-white dark:bg-[#0a0a0a] p-5 rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
          <div className="flex justify-between items-center">
            <div>
              <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold">System Uptime</p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{stats.systemUptime}</h3>
            </div>
            <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-500"><Server size={20} /></div>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Map Section */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white dark:bg-[#0a0a0a] p-4 rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <Globe size={18} className="text-blue-500" />
                Global Threat Map
              </h3>
              <div className="flex gap-2">
                <span className="flex items-center gap-1 text-[10px] text-slate-500"><span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>Auth Fail</span>
                <span className="flex items-center gap-1 text-[10px] text-slate-500"><span className="w-1.5 h-1.5 rounded-full bg-orange-500"></span>Command</span>
              </div>
            </div>
            <ThreatMap onRegionClick={setSelectedRegion} selectedRegion={selectedRegion} />
          </div>
        </div>

        {/* Live Feed Section */}
        <div className="lg:col-span-1 lg:relative min-h-[400px] lg:min-h-0">
          <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm h-full flex flex-col lg:absolute lg:inset-0">
            <div className="p-4 border-b border-slate-200 dark:border-white/5">
              <h3 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <Activity size={18} className="text-green-500" />
                Live Activity
              </h3>
            </div>
            <div className="p-2 flex-1 min-h-0">
              <AttackLog selectedRegion={selectedRegion} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
