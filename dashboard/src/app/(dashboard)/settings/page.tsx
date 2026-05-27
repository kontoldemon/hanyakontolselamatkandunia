"use client";

import { Shield, Zap, Fingerprint, Database, Save, Activity, ChevronDown, Check, Power } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { useSensorOperations, useSocketTelemetry } from "@/lib/liveEvents";

function CustomDropdown({ options, defaultValue }: { options: string[], defaultValue: string }) {
    const [isOpen, setIsOpen] = useState(false);
    const [selected, setSelected] = useState(defaultValue);
    const dropdownRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    return (
        <div className={`relative ${isOpen ? 'z-50' : 'z-10'}`} ref={dropdownRef}>
            <button 
                type="button"
                className="w-full bg-white dark:bg-[#121212] border border-slate-200 dark:border-white/10 rounded-lg p-2.5 outline-none focus:ring-2 focus:ring-indigo-500/50 flex justify-between items-center text-sm shadow-sm transition-all text-slate-700 dark:text-slate-200"
                onClick={() => setIsOpen(!isOpen)}
            >
                <span className="truncate pr-4">{selected}</span>
                <ChevronDown size={16} className={`text-slate-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
            </button>
            {isOpen && (
                <div className="absolute z-50 w-full mt-1.5 bg-white dark:bg-[#1a1a1a] border border-slate-200 dark:border-white/10 rounded-lg shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                    <ul className="max-h-60 overflow-y-auto py-1">
                        {options.map((opt) => (
                            <li 
                                key={opt}
                                className={`px-4 py-2.5 text-sm cursor-pointer flex justify-between items-center transition-colors ${selected === opt ? 'bg-indigo-50/50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 font-medium' : 'hover:bg-slate-50 dark:hover:bg-white/5 text-slate-700 dark:text-slate-300'}`}
                                onClick={() => {
                                    setSelected(opt);
                                    setIsOpen(false);
                                }}
                            >
                                <span className="truncate">{opt}</span>
                                {selected === opt && <Check size={16} />}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}

export default function SettingsPage() {
    const operations = useSensorOperations();
    const socketTelemetry = useSocketTelemetry();
    const [exposurePaused, setExposurePaused] = useState(false);
    const [exposureBusy, setExposureBusy] = useState(false);
    const upstreamLatency = operations?.telemetry?.upstreamLatencyMs ?? {};
    const latencyRows = [
        { name: "Readiness", value: Number(upstreamLatency.readiness ?? 0) },
        { name: "Metrics", value: Number(upstreamLatency.metrics ?? 0) },
        { name: "Stats", value: Number(upstreamLatency.stats ?? 0) },
        { name: "Sessions", value: Number(upstreamLatency.sessions ?? 0) },
        { name: "Distribution", value: Number(upstreamLatency.distribution ?? 0) },
        { name: "Attack Graph", value: Number(upstreamLatency.attackGraph ?? 0) },
        { name: "Anomaly", value: Number(upstreamLatency.anomaly ?? 0) },
        { name: "LLM", value: Number(upstreamLatency.llm ?? 0) },
    ];

    async function toggleExposure() {
        const nextPaused = !exposurePaused;
        const confirmed = window.confirm(nextPaused
            ? "Pause public honeypot exposure? Admin dashboard will stay online."
            : "Resume public honeypot exposure?");
        if (!confirmed) {
            return;
        }
        setExposureBusy(true);
        try {
            const response = await fetch("/api/cloudsentinel/exposure", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ enabled: !nextPaused }),
            });
            const data = await response.json();
            if (data.ok) {
                setExposurePaused(Boolean(data.paused));
            } else {
                window.alert(data.error ?? "Exposure update failed");
            }
        } catch {
            window.alert("Exposure update failed");
        } finally {
            setExposureBusy(false);
        }
    }

    return (
        <div className="max-w-6xl mx-auto flex flex-col h-full gap-6 pb-6">
            <div className="flex justify-between items-end shrink-0">
                <div>
                    <h2 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-500 bg-clip-text text-transparent">System Configuration</h2>
                    <p className="text-slate-500 text-xs mt-0.5">Manage CloudSentinel&apos;s event-driven deception and automated SOAR response.</p>
                </div>
                <button className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white px-4 py-1.5 rounded-lg text-xs font-semibold transition-colors shadow-sm">
                    <Save size={14} />
                    Apply Changes
                </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0 overflow-y-auto pr-1 terminal-scrollbar">
                
                {/* Left Column: Telemetry & Controls */}
                <div className="space-y-6 flex flex-col">
                    <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm p-4 flex flex-col gap-3">
                        <div className="flex items-start justify-between gap-4">
                            <div>
                                <h3 className="font-semibold text-sm flex items-center gap-2 text-amber-600 dark:text-amber-500">
                                    <Power size={16} />
                                    Exposure Control
                                </h3>
                                <p className="text-[10px] text-slate-500 mt-1">
                                    {operations?.source === "live" ? "Admin API connected. Toggle public honeypot traffic." : "Sensor API offline."}
                                </p>
                            </div>
                            <button
                                type="button"
                                disabled={exposureBusy || operations?.source !== "live"}
                                onClick={toggleExposure}
                                className={`shrink-0 inline-flex items-center justify-center gap-1.5 rounded px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider transition-colors disabled:opacity-50 ${exposurePaused ? "bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 border border-emerald-500/20" : "bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 border border-amber-500/20"}`}
                            >
                                <Power size={12} />
                                {exposurePaused ? "Resume" : "Pause"}
                            </button>
                        </div>
                    </div>

                    <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm flex-1 flex flex-col overflow-hidden">
                        <div className="p-4 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] shrink-0">
                            <h3 className="font-semibold text-sm flex items-center gap-2 text-slate-800 dark:text-slate-200">
                                <Activity size={16} className="text-blue-500" />
                                Pipeline Latency
                            </h3>
                        </div>
                        <div className="p-4 flex-1 overflow-y-auto space-y-2">
                            {latencyRows.map((row) => (
                                <div key={row.name} className="flex items-center justify-between text-[11px] rounded bg-slate-50 dark:bg-[#0f0f0f] border border-slate-200 dark:border-white/5 px-3 py-1.5">
                                    <span className="text-slate-600 dark:text-slate-400">{row.name}</span>
                                    <span className="font-mono text-slate-900 dark:text-slate-300 font-medium">{row.value}ms</span>
                                </div>
                            ))}
                        </div>
                        <div className="p-3 border-t border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] shrink-0 text-[10px] text-slate-500 flex justify-between">
                            <span>Max: <span className="font-mono">{Number(operations?.telemetry?.maxLatencyMs ?? 0)}ms</span></span>
                            <span className="truncate ml-2">Sync: {operations?.telemetry?.sampledAt ?? "n/a"}</span>
                        </div>
                    </div>
                </div>

                {/* Right Column (Span 2): Configurations & Socket Logs */}
                <div className="lg:col-span-2 space-y-6 flex flex-col">
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 shrink-0">
                        {/* Deception Sensor */}
                        <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
                            <div className="p-4 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02]">
                                <h3 className="font-semibold text-sm flex items-center gap-2 text-indigo-500">
                                    <Database size={16} /> Sensor Node (AsyncSSH)
                                </h3>
                            </div>
                            <div className="p-4 space-y-4">
                                <div>
                                    <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Deception Level</label>
                                    <CustomDropdown 
                                        options={["High (Full VFS)", "Medium (Restricted)", "Low (Port listener)"]}
                                        defaultValue="High (Full VFS)"
                                    />
                                </div>
                                <div className="pt-2">
                                    <label className="flex items-center gap-2 cursor-pointer group">
                                        <div className="relative flex items-center justify-center w-4 h-4 rounded border border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-[#0f0f0f] group-hover:border-indigo-500 transition-colors">
                                            <input type="checkbox" defaultChecked className="opacity-0 absolute inset-0 cursor-pointer" />
                                            <Check size={12} className="text-indigo-500 opacity-100" />
                                        </div>
                                        <span className="text-[11px] font-medium text-slate-700 dark:text-slate-300">Inject Fake AWS API Keys (bash_history)</span>
                                    </label>
                                </div>
                            </div>
                        </div>

                        {/* HASSH Engine */}
                        <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
                            <div className="p-4 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02]">
                                <h3 className="font-semibold text-sm flex items-center gap-2 text-purple-500">
                                    <Fingerprint size={16} /> Identity Engine (HASSH)
                                </h3>
                            </div>
                            <div className="p-4 space-y-4">
                                <div>
                                    <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Malicious HASSH Action</label>
                                    <CustomDropdown 
                                        options={["Immediate Drop", "Allow & Monitor", "Tarpit"]}
                                        defaultValue="Immediate Drop"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Confidence Threshold</label>
                                    <div className="flex items-center gap-3">
                                        <input type="range" min="0" max="100" defaultValue="85" className="flex-1 accent-purple-500 h-1 bg-slate-200 dark:bg-slate-800 rounded-full appearance-none outline-none" />
                                        <span className="text-[11px] font-mono font-bold w-8 text-right text-slate-700 dark:text-slate-300">85%</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* SOAR Config */}
                    <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm shrink-0">
                        <div className="p-4 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] flex justify-between items-center">
                            <h3 className="font-semibold text-sm flex items-center gap-2 text-rose-500">
                                <Zap size={16} /> Automated SOAR Response
                            </h3>
                            <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 text-[10px] font-bold uppercase tracking-wider border border-rose-500/20">Active</span>
                        </div>
                        <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div>
                                <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Trigger Condition</label>
                                <CustomDropdown options={["MITRE Match (>1)", "Auth Spike (>10/m)", "Any Input"]} defaultValue="MITRE Match (>1)" />
                            </div>
                            <div>
                                <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Execution Path</label>
                                <CustomDropdown options={["Lambda (Warm)", "Lambda (Cold)", "Local Docker"]} defaultValue="Lambda (Warm)" />
                            </div>
                            <div>
                                <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Action Applied</label>
                                <div className="border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-[#0f0f0f] rounded-lg px-3 py-2 flex items-center gap-2">
                                    <Shield size={14} className="text-slate-400 shrink-0" />
                                    <span className="text-xs font-mono text-slate-700 dark:text-slate-300 truncate">Revoke IP (Security Group)</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Socket Logs */}
                    <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm flex-1 flex flex-col min-h-[200px] overflow-hidden">
                        <div className="p-3 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] flex justify-between items-center shrink-0">
                            <h3 className="font-semibold text-sm text-slate-800 dark:text-slate-200">Socket Telemetry</h3>
                            <div className="flex gap-3 text-[10px] font-mono text-slate-500">
                                <span>Conn: {socketTelemetry.connectCount}</span>
                                <span>Drop: {socketTelemetry.disconnectCount}</span>
                                <span className={socketTelemetry.connected ? "text-emerald-500 font-bold" : "text-amber-500 font-bold"}>
                                    {socketTelemetry.connected ? "ONLINE" : "OFFLINE"}
                                </span>
                            </div>
                        </div>
                        <div className="flex-1 overflow-y-auto p-3 space-y-1 terminal-scrollbar bg-slate-50/30 dark:bg-[#050505]">
                            {socketTelemetry.recent.length === 0 && (
                                <div className="text-[11px] text-slate-500 text-center py-4">No socket events captured yet.</div>
                            )}
                            {socketTelemetry.recent.map((entry, index) => (
                                <div key={`${entry.timestamp}-${index}`} className="flex items-start gap-2 text-[10px] font-mono border-b border-slate-100 dark:border-white/5 py-1.5 last:border-0">
                                    <span className="text-slate-400 shrink-0">{entry.timestamp.split('T')[1]?.replace('Z', '')}</span>
                                    <span className={`shrink-0 w-12 font-bold ${entry.level === "error" ? "text-red-500" : entry.level === "warn" ? "text-amber-500" : "text-emerald-500"}`}>
                                        [{entry.level}]
                                    </span>
                                    <span className="text-slate-700 dark:text-slate-300 font-semibold">{entry.event}</span>
                                    {entry.detail && <span className="text-slate-500 break-all">{entry.detail}</span>}
                                </div>
                            ))}
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
}
