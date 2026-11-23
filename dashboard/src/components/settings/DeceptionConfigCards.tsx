"use client";

import { Check, Database, Fingerprint, Maximize2, Minimize2, Shield, Zap } from "lucide-react";
import type { SocketTelemetrySnapshot } from "@/lib/liveEvents";
import CustomDropdown from "@/components/ui/CustomDropdown";

interface DeceptionConfigCardsProps {
    deceptionLevel: string;
    onDeceptionLevelChange: (v: string) => void;
    fakeKeys: boolean;
    onToggleFakeKeys: () => void;
    hasshAction: string;
    onHasshActionChange: (v: string) => void;
    hasshThreshold: number;
    onHasshThresholdChange: (v: number) => void;
    soarTrigger: string;
    onSoarTriggerChange: (v: string) => void;
    soarExecution: string;
    onSoarExecutionChange: (v: string) => void;
    socketTelemetry: SocketTelemetrySnapshot;
    isSocketFullScreen: boolean;
    onToggleSocketFullScreen: () => void;
    onExitSocketFullScreen: () => void;
}

export default function DeceptionConfigCards({
    deceptionLevel,
    onDeceptionLevelChange,
    fakeKeys,
    onToggleFakeKeys,
    hasshAction,
    onHasshActionChange,
    hasshThreshold,
    onHasshThresholdChange,
    soarTrigger,
    onSoarTriggerChange,
    soarExecution,
    onSoarExecutionChange,
    socketTelemetry,
    isSocketFullScreen,
    onToggleSocketFullScreen,
    onExitSocketFullScreen,
}: DeceptionConfigCardsProps) {
    return (
        <div className="lg:col-span-2 space-y-6 flex flex-col min-h-0">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 shrink-0">
                {/* Deception Sensor */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
                    <div className="p-4 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02]">
                        <h3 className="font-display font-semibold text-[13px] tracking-tight flex items-center gap-2 text-indigo-500">
                            <Database size={15} /> Sensor Node (AsyncSSH)
                        </h3>
                    </div>
                    <div className="p-4 space-y-4">
                        <div>
                            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Deception Level</label>
                            <CustomDropdown
                                options={[
                                    { label: "High (Full VFS)", value: "High (Full VFS)" },
                                    { label: "Medium (Restricted)", value: "Medium (Restricted)" },
                                    { label: "Low (Port listener)", value: "Low (Port listener)" },
                                ]}
                                value={deceptionLevel}
                                onChange={onDeceptionLevelChange}
                            />
                        </div>
                        <div className="pt-2">
                            <label className="flex items-center gap-2 cursor-pointer group">
                                <div className="relative flex items-center justify-center w-4 h-4 rounded border border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-[#0f0f0f] group-hover:border-indigo-500 transition-colors">
                                    <input type="checkbox" checked={fakeKeys} onChange={onToggleFakeKeys} className="opacity-0 absolute inset-0 cursor-pointer" />
                                    {fakeKeys && <Check size={12} className="text-indigo-500 opacity-100" />}
                                </div>
                                <span className="text-[11px] font-medium text-slate-700 dark:text-slate-300">Inject Fake AWS API Keys (bash_history)</span>
                            </label>
                        </div>
                    </div>
                </div>

                {/* HASSH Engine */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
                    <div className="p-4 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02]">
                        <h3 className="font-display font-semibold text-[13px] tracking-tight flex items-center gap-2 text-purple-500">
                            <Fingerprint size={15} /> Identity Engine (HASSH)
                        </h3>
                    </div>
                    <div className="p-4 space-y-4">
                        <div>
                            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Malicious HASSH Action</label>
                            <CustomDropdown
                                options={[
                                    { label: "Immediate Drop", value: "Immediate Drop" },
                                    { label: "Allow & Monitor", value: "Allow & Monitor" },
                                    { label: "Tarpit", value: "Tarpit" },
                                ]}
                                value={hasshAction}
                                onChange={onHasshActionChange}
                            />
                        </div>
                        <div>
                            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Confidence Threshold</label>
                            <div className="flex items-center gap-3">
                                <input
                                    type="range"
                                    min="0"
                                    max="100"
                                    value={hasshThreshold}
                                    onChange={(e) => onHasshThresholdChange(parseInt(e.target.value, 10))}
                                    className="flex-1 accent-purple-500 h-1 bg-slate-200 dark:bg-slate-800 rounded-full appearance-none outline-none"
                                />
                                <span className="text-[11px] font-mono font-bold w-8 text-right text-slate-700 dark:text-slate-300">{hasshThreshold}%</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* SOAR Config */}
            <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm shrink-0">
                <div className="p-4 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] flex justify-between items-center">
                    <h3 className="font-display font-semibold text-[13px] tracking-tight flex items-center gap-2 text-rose-500">
                        <Zap size={15} /> Automated SOAR Response
                    </h3>
                    <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 text-[10px] font-bold uppercase tracking-wider border border-rose-500/20">Active</span>
                </div>
                <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                        <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Trigger Condition</label>
                        <CustomDropdown
                            options={[
                                { label: "MITRE Match (>1)", value: "MITRE Match (>1)" },
                                { label: "Auth Spike (>10/m)", value: "Auth Spike (>10/m)" },
                                { label: "Any Input", value: "Any Input" },
                            ]}
                            value={soarTrigger}
                            onChange={onSoarTriggerChange}
                        />
                    </div>
                    <div>
                        <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Execution Path</label>
                        <CustomDropdown
                            options={[
                                { label: "Lambda (Warm)", value: "Lambda (Warm)" },
                                { label: "Lambda (Cold)", value: "Lambda (Cold)" },
                                { label: "Local Docker", value: "Local Docker" },
                            ]}
                            value={soarExecution}
                            onChange={onSoarExecutionChange}
                        />
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
            <div className={isSocketFullScreen ? "fixed inset-4 z-[120] bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-2xl flex flex-col overflow-hidden" : "bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm flex-1 min-h-0 flex flex-col overflow-hidden"}>
                {isSocketFullScreen && <div className="fixed inset-0 z-[-1] bg-black/60 backdrop-blur-sm" onClick={onExitSocketFullScreen} />}
                <div className="p-3 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] flex justify-between items-center shrink-0">
                    <h3 className="font-display font-semibold text-[13px] tracking-tight text-slate-800 dark:text-slate-200">Socket Telemetry</h3>
                    <div className="flex items-center gap-3">
                        <div className="flex gap-3 text-[10px] font-mono text-slate-500 mr-2">
                            <span>Conn: {socketTelemetry.connectCount}</span>
                            <span>Drop: {socketTelemetry.disconnectCount}</span>
                            <span className={socketTelemetry.connected ? "text-emerald-500 font-bold" : "text-amber-500 font-bold"}>
                                {socketTelemetry.connected ? "ONLINE" : "OFFLINE"}
                            </span>
                        </div>
                        <button onClick={onToggleSocketFullScreen} className="p-1 text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300 transition-colors rounded hover:bg-slate-200 dark:hover:bg-white/10" title={isSocketFullScreen ? "Exit Fullscreen" : "Fullscreen"}>
                            {isSocketFullScreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                        </button>
                    </div>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-1 terminal-scrollbar bg-slate-50/30 dark:bg-[#050505]">
                    {socketTelemetry.recent.length === 0 && (
                        <div className="text-[11px] text-slate-500 text-center py-4">No socket events captured yet.</div>
                    )}
                    {socketTelemetry.recent.map((entry, index) => (
                        <div key={`${entry.timestamp}-${index}`} className="flex items-start gap-2 text-[10px] font-mono border-b border-slate-100 dark:border-white/5 py-1.5 last:border-0">
                            <span className="text-slate-400 shrink-0">{entry.timestamp.split("T")[1]?.replace("Z", "")}</span>
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
    );
}
