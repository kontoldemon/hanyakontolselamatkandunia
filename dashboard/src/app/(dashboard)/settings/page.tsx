"use client";

import { Shield, Zap, Fingerprint, Database, Save, Activity, ChevronDown, Check } from "lucide-react";
import { useState, useRef, useEffect } from "react";

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
    return (
        <div className="max-w-5xl mx-auto space-y-6 pb-12">
            <div>
                <h2 className="text-2xl font-bold font-mono">System Configuration</h2>
                <p className="text-slate-500 text-sm mt-1">Manage CloudSentinel&apos;s event-driven deception and automated SOAR response.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Deception Sensor (AsyncSSH) */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm flex flex-col">
                    <div className="p-5 border-b border-slate-200 dark:border-white/5 bg-slate-50 dark:bg-white/[0.02] rounded-t-xl">
                        <h3 className="font-bold flex items-center gap-2 text-indigo-600 dark:text-indigo-400">
                            <Database size={18} />
                            Sensor Node (AsyncSSH)
                        </h3>
                        <p className="text-xs text-slate-500 mt-1">Configure the AWS EC2 trap environment properties.</p>
                    </div>
                    <div className="p-5 space-y-5 flex-1">
                        <div>
                            <label className="block text-sm font-medium mb-2 opacity-80">Deception Level (VFS)</label>
                            <CustomDropdown 
                                options={["High Interaction (Full Ubuntu 22.04 VFS)", "Medium Interaction (Restricted Sandbox)", "Low Interaction (Port listener only)"]}
                                defaultValue="High Interaction (Full Ubuntu 22.04 VFS)"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2 opacity-80 flex justify-between">
                                <span>Honey-token Deployment</span>
                                <span className="text-[10px] bg-green-500/20 text-green-600 dark:text-green-400 px-2 py-0.5 rounded uppercase font-bold tracking-wider">Active</span>
                            </label>
                            <div className="flex items-center gap-3 bg-slate-100 dark:bg-white/5 p-3.5 border border-slate-200 dark:border-white/10 rounded-lg">
                                <input type="checkbox" defaultChecked className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600 bg-white" />
                                <span className="text-sm font-medium">Inject Fake AWS API Keys into bash_history</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Identity-Centric Engine (HASSH) */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm flex flex-col">
                    <div className="p-5 border-b border-slate-200 dark:border-white/5 bg-slate-50 dark:bg-white/[0.02] rounded-t-xl">
                        <h3 className="font-bold flex items-center gap-2 text-blue-600 dark:text-blue-400">
                            <Fingerprint size={18} />
                            Identity-Centric Engine (HASSH)
                        </h3>
                        <p className="text-xs text-slate-500 mt-1">Manage cryptographic botnet fingerprinting and DNA profiling.</p>
                    </div>
                    <div className="p-5 space-y-5 flex-1">
                        <div>
                            <label className="block text-sm font-medium mb-2 opacity-80">Action on Known Malicious HASSH</label>
                            <CustomDropdown 
                                options={["Immediate Drop (Pre-Auth)", "Allow & Monitor (Intelligence Gathering)", "Tarpit (Slow response)"]}
                                defaultValue="Immediate Drop (Pre-Auth)"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2 opacity-80">False Positive Mitigation</label>
                            <div className="flex items-center gap-4 bg-slate-100 dark:bg-white/5 p-3 border border-slate-200 dark:border-white/10 rounded-lg">
                                <input type="range" min="0" max="100" defaultValue="85" className="w-full accent-blue-600" />
                                <span className="text-sm font-mono font-bold w-12 text-right">85%</span>
                            </div>
                            <p className="text-[10px] text-slate-400 mt-1.5 ml-1">Minimum confidence score required to auto-ban a new HASSH.</p>
                        </div>
                    </div>
                </div>

                {/* Event-Driven SOAR */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm lg:col-span-2">
                    <div className="p-5 border-b border-slate-200 dark:border-white/5 bg-slate-50 dark:bg-white/[0.02] rounded-t-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div>
                            <h3 className="font-bold flex items-center gap-2 text-rose-600 dark:text-rose-500">
                                <Zap size={18} />
                                Automated SOAR Response (AWS Lambda)
                            </h3>
                            <p className="text-xs text-slate-500 mt-1">Configure event boundaries and auto-blocking thresholds (Target MTTB: &lt;0.86s).</p>
                        </div>
                        <div className="flex items-center w-fit gap-2 px-3 py-1 bg-rose-500/10 text-rose-600 dark:text-rose-400 rounded-full text-xs font-bold border border-rose-500/20">
                            <Activity size={12} className="animate-pulse" /> Live Execution
                        </div>
                    </div>
                    <div className="p-5 grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div>
                            <label className="block text-sm font-medium mb-2 opacity-80">Event Trigger (EventBridge)</label>
                            <CustomDropdown 
                                options={["MITRE TTP Matched (>1)", "Failed Auth Spike (>10/min)", "Any Interaction"]}
                                defaultValue="MITRE TTP Matched (>1)"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2 opacity-80">Execution Pathway</label>
                            <CustomDropdown 
                                options={["Lambda (Provisioned Concurrency)", "Lambda (Standard Cold Start)", "Local Docker Container"]}
                                defaultValue="Lambda (Provisioned Concurrency)"
                            />
                            <p className="text-[10px] text-slate-400 mt-1.5 ml-1">Provisioned Concurrency ensures MTTB translates to under 1s.</p>
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2 opacity-80">Response Action</label>
                            <div className="border border-slate-200 dark:border-white/10 bg-slate-100 dark:bg-white/5 rounded-lg p-2.5 flex items-center gap-2 h-11">
                                <Shield size={16} className="text-slate-400" />
                                <span className="text-sm font-mono font-medium truncate">Revoke IP via Security Group</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div className="flex justify-end pt-4">
                <button className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-lg font-medium transition-colors shadow-lg shadow-blue-500/20 active:scale-95">
                    <Save size={18} />
                    Apply Configuration
                </button>
            </div>
        </div>
    );
}
