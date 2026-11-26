"use client";

import { Fingerprint, Terminal } from "lucide-react";
import CustomDropdown from "@/components/ui/CustomDropdown";
import ToggleSwitch from "./ToggleSwitch";

interface DeceptionSectionProps {
    deceptionLevel: string;
    setDeceptionLevel: (v: string) => void;
    fakeKeys: boolean;
    setFakeKeys: (v: boolean) => void;
    hasshAction: string;
    setHasshAction: (v: string) => void;
    hasshThreshold: number;
    setHasshThreshold: (v: number) => void;
}

export default function DeceptionSection({
    deceptionLevel,
    setDeceptionLevel,
    fakeKeys,
    setFakeKeys,
    hasshAction,
    setHasshAction,
    hasshThreshold,
    setHasshThreshold,
}: DeceptionSectionProps) {
    return (
        <section id="sec-deception" className="space-y-3.5 scroll-mt-2 animate-in fade-in duration-150">
            <div className="space-y-3.5">
                {/* Sensor Parameters */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden">
                    <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015]">
                        <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                            <Terminal size={14} className="text-blue-500" /> Sensor Node (AsyncSSH)
                        </h3>
                    </div>
                    <div className="divide-y divide-slate-100 dark:divide-white/5">
                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex flex-col items-stretch sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3">
                            <div className="min-w-0 sm:pr-2">
                                <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">Deception Emulation Depth</label>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">Honeypot virtual filesystem depth.</p>
                            </div>
                            <div className="w-full sm:w-56 shrink-0">
                                <CustomDropdown
                                    options={[
                                        { label: "High (Full VFS)", value: "full" },
                                        { label: "Medium (Restricted)", value: "restricted" },
                                        { label: "Low (Port listener)", value: "listener" },
                                    ]}
                                    value={deceptionLevel}
                                    onChange={setDeceptionLevel}
                                />
                            </div>
                        </div>

                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex items-center justify-between gap-3">
                            <div className="min-w-0 pr-2">
                                <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">Seed Canary API Keys</label>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">Inject fake AWS credentials in bash history.</p>
                            </div>
                            <ToggleSwitch checked={fakeKeys} onChange={setFakeKeys} />
                        </div>
                    </div>
                </div>

                {/* HASSH Fingerprinting */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden">
                    <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015]">
                        <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                            <Fingerprint size={14} className="text-purple-500" /> Identity Engine (HASSH)
                        </h3>
                    </div>
                    <div className="divide-y divide-slate-100 dark:divide-white/5">
                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex flex-col items-stretch sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3">
                            <div className="min-w-0 sm:pr-2">
                                <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">Malicious HASSH Action</label>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">Mitigation for matched client signatures.</p>
                            </div>
                            <div className="w-full sm:w-56 shrink-0">
                                <CustomDropdown
                                    options={[
                                        { label: "Immediate Drop", value: "drop" },
                                        { label: "Allow & Monitor", value: "monitor" },
                                    ]}
                                    value={hasshAction}
                                    onChange={setHasshAction}
                                />
                            </div>
                        </div>

                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex flex-col items-stretch sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3">
                            <div className="min-w-0 sm:pr-2">
                                <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">Matching Confidence</label>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">Minimum confidence required.</p>
                            </div>
                            <div className="w-full sm:w-56 flex items-center gap-3 shrink-0">
                                <input
                                    type="range"
                                    min="0"
                                    max="100"
                                    value={hasshThreshold}
                                    onChange={(e) => setHasshThreshold(parseInt(e.target.value, 10))}
                                    style={{
                                        background: `linear-gradient(to right, rgb(168 85 247) 0%, rgb(168 85 247) ${hasshThreshold}%, rgba(148, 163, 184, 0.2) ${hasshThreshold}%, rgba(148, 163, 184, 0.2) 100%)`,
                                    }}
                                    className="w-full h-1 rounded-full appearance-none outline-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-2.5 [&::-webkit-slider-thumb]:h-2.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-purple-500 [&::-webkit-slider-thumb]:hover:scale-125 [&::-webkit-slider-thumb]:transition-all"
                                />
                                <span className="font-mono text-xs font-bold text-slate-700 dark:text-slate-300 w-9 text-right shrink-0">{hasshThreshold}%</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
