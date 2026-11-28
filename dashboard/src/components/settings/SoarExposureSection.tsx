"use client";

import { Power, Zap } from "lucide-react";
import CustomDropdown from "@/components/ui/CustomDropdown";
import { cn } from "@/lib/utils";

interface SoarExposureSectionProps {
    soarTrigger: string;
    setSoarTrigger: (v: string) => void;
    soarExecution: string;
    setSoarExecution: (v: string) => void;
    exposurePaused: boolean;
    exposureBusy: boolean;
    exposureSyncing: boolean;
    exposureCooldownActive: boolean;
    cooldownRemainingSec: number;
    sensorOnline: boolean;
    effectiveExposureEnabled?: boolean | null;
    openExposureConfirm: () => void;
}

export default function SoarExposureSection({
    soarTrigger,
    setSoarTrigger,
    soarExecution,
    setSoarExecution,
    exposurePaused,
    exposureBusy,
    exposureSyncing,
    exposureCooldownActive,
    cooldownRemainingSec,
    sensorOnline,
    effectiveExposureEnabled,
    openExposureConfirm,
}: SoarExposureSectionProps) {
    return (
        <section id="sec-soar" className="space-y-3.5 scroll-mt-2 animate-in fade-in duration-150">
            <div className="space-y-3.5">
                {/* Exposure Gateway */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden">
                    <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015]">
                        <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                            <Power size={14} className="text-blue-500" /> Ingress Exposure Control
                        </h3>
                    </div>
                    <div className="divide-y divide-slate-100 dark:divide-white/5">
                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex flex-col items-start sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3">
                            <div className="min-w-0 sm:pr-2">
                                <div className="flex items-center gap-1.5">
                                    <label className="text-xs font-semibold text-slate-900 dark:text-white">Public Ingress Forwarding</label>
                                    <span
                                        className={cn(
                                            "w-2 h-2 rounded-full",
                                            effectiveExposureEnabled === false
                                                ? "bg-amber-500"
                                                : effectiveExposureEnabled === true
                                                    ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)]"
                                                    : "bg-slate-400"
                                        )}
                                        title={effectiveExposureEnabled === false ? "Gateway Offline" : effectiveExposureEnabled === true ? "Gateway Active" : "Gateway state unknown"}
                                    />
                                </div>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">
                                    {sensorOnline
                                        ? "Sensor API active. Toggling offline detaches public IP forwarding rules immediately."
                                        : "Sensor API unreachable. Ingress status cannot be modified."}
                                </p>
                            </div>
                            <button
                                type="button"
                                disabled={exposureBusy || exposureSyncing || exposureCooldownActive || !sensorOnline}
                                onClick={openExposureConfirm}
                                className={cn(
                                    "h-9 sm:h-7 inline-flex items-center gap-1.5 rounded-lg px-2.5 text-[11px] font-medium transition-all shadow-xs disabled:opacity-50 cursor-pointer shrink-0",
                                    exposurePaused
                                        ? "bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                                        : "bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/20"
                                )}
                            >
                                <Power size={11} />
                                <span>
                                    {exposureBusy || exposureSyncing
                                        ? "Applying..."
                                        : exposureCooldownActive
                                            ? `Cooldown ${cooldownRemainingSec}s`
                                            : exposurePaused
                                                ? "Set Online"
                                                : "Set Offline"}
                                </span>
                            </button>
                        </div>
                    </div>
                </div>

                {/* SOAR Containment Pipeline */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden">
                    <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015]">
                        <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                            <Zap size={14} className="text-blue-500" /> Automated SOAR Pipeline
                        </h3>
                    </div>
                    <div className="divide-y divide-slate-100 dark:divide-white/5">
                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex flex-col items-stretch sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3">
                            <div className="min-w-0 sm:pr-2">
                                <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">Containment Trigger</label>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">Pattern required for network isolation.</p>
                            </div>
                            <div className="w-full sm:w-56 shrink-0">
                                <CustomDropdown
                                    options={[
                                        { label: "Risk Score Threshold", value: "risk" },
                                        { label: "MITRE Match (>1)", value: "mitre" },
                                        { label: "Auth Spike (>10/m)", value: "auth_spike" },
                                        { label: "Any Input", value: "any_input" },
                                    ]}
                                    value={soarTrigger}
                                    onChange={setSoarTrigger}
                                />
                            </div>
                        </div>

                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex flex-col items-stretch sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3">
                            <div className="min-w-0 sm:pr-2">
                                <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">Execution Runtime</label>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">Async task execution engine.</p>
                            </div>
                            <div className="w-full sm:w-56 shrink-0">
                                <CustomDropdown
                                    options={[
                                        { label: "Azure Function (Event Grid)", value: "eventgrid" },
                                        { label: "Host Netfilter Daemon", value: "host" },
                                    ]}
                                    value={soarExecution}
                                    onChange={setSoarExecution}
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
