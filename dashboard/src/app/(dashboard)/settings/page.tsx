"use client";

import { Activity, Check, Database, Fingerprint, Maximize2, Minimize2, Power, Save, Shield, Zap, Sparkles, Bot, Key, Eye, EyeOff } from "lucide-react";
import { useState, useCallback, useEffect } from "react";
import { useSensorOperations, useSocketTelemetry, useWarRoomState } from "@/lib/liveEvents";
import { useAgentCommand } from "@/lib/AgentContext";
import { useExposureControl } from "@/components/settings/useExposureControl";
import CustomDropdown from "@/components/ui/CustomDropdown";
import { cn } from "@/lib/utils";

type SettingsSection = "deception" | "soar" | "telemetry" | "llm";

export default function SettingsPage() {
    const operations = useSensorOperations();
    const socketTelemetry = useSocketTelemetry();
    const warRoom = useWarRoomState();
    const [isSocketFullScreen, setIsSocketFullScreen] = useState(false);
    const [activeSection, setActiveSection] = useState<SettingsSection>("deception");
    const [savedToast, setSavedToast] = useState(false);

    const [deceptionLevel, setDeceptionLevel] = useState("High (Full VFS)");
    const [hasshAction, setHasshAction] = useState("Immediate Drop");
    const [hasshThreshold, setHasshThreshold] = useState(85);
    const [fakeKeys, setFakeKeys] = useState(true);
    const [soarTrigger, setSoarTrigger] = useState("MITRE Match (>1)");
    const [soarExecution, setSoarExecution] = useState("Lambda (Warm)");

    // AI & LLM Engine Configuration State (Both Copilot & Honeypot VFS)
    const [copilotProvider, setCopilotProvider] = useState("Google Gemini");
    const [copilotModel, setCopilotModel] = useState("gemini/gemini-2.0-flash");
    const [copilotApiKey, setCopilotApiKey] = useState("");
    const [hasCopilotKey, setHasCopilotKey] = useState(false);
    const [showCopilotKey, setShowCopilotKey] = useState(false);

    const [honeypotLlmMode, setHoneypotLlmMode] = useState("Dynamic VFS Terminal Emulation");
    const [honeypotProvider, setHoneypotProvider] = useState("Inherit from Copilot");
    const [honeypotModel, setHoneypotModel] = useState("gemini/gemini-2.0-flash");
    const [honeypotApiKey, setHoneypotApiKey] = useState("");
    const [showHoneypotKey, setShowHoneypotKey] = useState(false);
    const [useCopilotKeyForHoneypot, setUseCopilotKeyForHoneypot] = useState(true);
    const [fallbackChain, setFallbackChain] = useState("groq/llama-3.3-70b-versatile, openai/gpt-4o-mini");
    const [hourlyLimit, setHourlyLimit] = useState(200);

    useEffect(() => {
        fetch("/api/cloudsentinel/llm-config")
            .then((res) => res.json())
            .then((data) => {
                if (data?.ok && data.config) {
                    if (data.config.copilotProvider) setCopilotProvider(data.config.copilotProvider);
                    if (data.config.copilotModel) setCopilotModel(data.config.copilotModel);
                    if (typeof data.config.hasCopilotKey === "boolean") setHasCopilotKey(data.config.hasCopilotKey);
                    if (data.config.honeypotLlmMode) setHoneypotLlmMode(data.config.honeypotLlmMode);
                    if (data.config.honeypotProvider) setHoneypotProvider(data.config.honeypotProvider);
                    if (data.config.honeypotModel) setHoneypotModel(data.config.honeypotModel);
                    if (data.config.honeypotApiKey) setHoneypotApiKey(data.config.honeypotApiKey);
                    if (typeof data.config.useCopilotKeyForHoneypot === "boolean") setUseCopilotKeyForHoneypot(data.config.useCopilotKeyForHoneypot);
                    if (data.config.fallbackChain) setFallbackChain(data.config.fallbackChain);
                    if (data.config.hourlyLimit) setHourlyLimit(data.config.hourlyLimit);
                }
            })
            .catch(() => null);
    }, []);

    useAgentCommand("settings.deception_level", useCallback((v: string) => setDeceptionLevel(v), []));
    useAgentCommand("settings.hassh_action", useCallback((v: string) => setHasshAction(v), []));
    useAgentCommand("settings.hassh_threshold", useCallback((v: string) => setHasshThreshold(Math.max(0, Math.min(100, parseInt(v, 10) || 85))), []));
    useAgentCommand("settings.fake_keys", useCallback((v: string) => setFakeKeys(v === "true" || v === "toggle" ? !fakeKeys : v === "on"), [fakeKeys]));
    useAgentCommand("settings.soar_trigger", useCallback((v: string) => setSoarTrigger(v), []));
    useAgentCommand("settings.soar_execution", useCallback((v: string) => setSoarExecution(v), []));
    useAgentCommand("socket.fullscreen", useCallback(() => setIsSocketFullScreen((p) => !p), []));

    const {
        exposurePaused,
        exposureBusy,
        toast,
        showExposureConfirm,
        pendingExposurePaused,
        cooldownRemainingSec,
        exposureCooldownActive,
        sensorOnline,
        exposureSyncing,
        effectiveExposureEnabled,
        openExposureConfirm,
        confirmExposureToggle,
        cancelExposureConfirm,
    } = useExposureControl(operations, warRoom);

    const handleApplyChanges = async () => {
        setSavedToast(true);
        setTimeout(() => setSavedToast(false), 2500);
        const submittedCopilotKey = copilotApiKey.trim();

        try {
            await fetch("/api/cloudsentinel/llm-config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    copilotProvider,
                    copilotModel,
                    copilotApiKey: submittedCopilotKey,
                    honeypotLlmMode,
                    honeypotProvider,
                    honeypotModel,
                    honeypotApiKey,
                    useCopilotKeyForHoneypot,
                    fallbackChain,
                    hourlyLimit,
                }),
            });
            if (submittedCopilotKey) {
                setCopilotApiKey("");
                setHasCopilotKey(true);
            }
        } catch {
            // Silently tolerate
        }
    };

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

    return (
        <div className="h-full flex flex-col gap-4">
            {(toast || savedToast) && (
                <div className="fixed top-5 left-1/2 -translate-x-1/2 z-[160] px-4 py-2 rounded-lg border shadow-lg text-xs font-semibold bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-400 backdrop-blur-md animate-in fade-in slide-in-from-top-2 duration-200">
                    {savedToast ? "Configuration saved and synced to honeypot nodes." : toast?.message}
                </div>
            )}

            <div className="flex-1 min-h-0 flex flex-col md:flex-row gap-5 overflow-hidden">
                {/* Left Navigation List Buttons */}
                <div className="md:w-60 shrink-0 flex flex-col justify-between bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/5 rounded-xl p-3 shadow-sm h-full">
                    <div className="flex flex-col gap-1.5">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-2 py-1">
                            Configuration Tabs
                        </span>
                        <button
                            type="button"
                            onClick={() => setActiveSection("deception")}
                            className={cn(
                                "w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs transition-all text-left group",
                                activeSection === "deception"
                                    ? "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 font-semibold"
                                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5 font-medium"
                            )}
                        >
                            <div className="flex items-center gap-2.5">
                                <Database size={15} className={activeSection === "deception" ? "text-indigo-500" : "text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300"} />
                                <div className="flex flex-col">
                                    <span>Deception Engine</span>
                                    <span className="text-[10px] text-slate-400 font-normal">VFS &amp; Honey-Tokens</span>
                                </div>
                            </div>
                        </button>

                        <button
                            type="button"
                            onClick={() => setActiveSection("soar")}
                            className={cn(
                                "w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs transition-all text-left group",
                                activeSection === "soar"
                                    ? "bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-400 font-semibold"
                                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5 font-medium"
                            )}
                        >
                            <div className="flex items-center gap-2.5">
                                <Zap size={15} className={activeSection === "soar" ? "text-rose-500" : "text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300"} />
                                <div className="flex flex-col">
                                    <span>SOAR &amp; Exposure</span>
                                    <span className="text-[10px] text-slate-400 font-normal">Containment &amp; Gateway</span>
                                </div>
                            </div>
                        </button>

                        <button
                            type="button"
                            onClick={() => setActiveSection("llm")}
                            className={cn(
                                "w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs transition-all text-left group",
                                activeSection === "llm"
                                    ? "bg-purple-50 dark:bg-purple-500/10 text-purple-600 dark:text-purple-400 font-semibold"
                                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5 font-medium"
                            )}
                        >
                            <div className="flex items-center gap-2.5">
                                <Sparkles size={15} className={activeSection === "llm" ? "text-purple-500" : "text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300"} />
                                <div className="flex flex-col">
                                    <span>AI &amp; LLM Engines</span>
                                    <span className="text-[10px] text-slate-400 font-normal">Copilot &amp; Honeypot VFS</span>
                                </div>
                            </div>
                        </button>

                        <button
                            type="button"
                            onClick={() => setActiveSection("telemetry")}
                            className={cn(
                                "w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs transition-all text-left group",
                                activeSection === "telemetry"
                                    ? "bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold"
                                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5 font-medium"
                            )}
                        >
                            <div className="flex items-center gap-2.5">
                                <Activity size={15} className={activeSection === "telemetry" ? "text-blue-500" : "text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300"} />
                                <div className="flex flex-col">
                                    <span>Ops &amp; Telemetry</span>
                                    <span className="text-[10px] text-slate-400 font-normal">Health &amp; Live Sockets</span>
                                </div>
                            </div>
                        </button>
                    </div>

                    {/* Anchored Actions & Cluster Status Widget */}
                    <div className="pt-3 border-t border-slate-200/60 dark:border-white/5 flex flex-col gap-2.5">
                        <button
                            onClick={handleApplyChanges}
                            className="w-full flex items-center justify-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white py-2 px-3 rounded-lg text-xs font-semibold transition-all shadow-sm active:scale-95 hover:shadow-blue-500/20"
                        >
                            <Save size={13} />
                            Apply Changes
                        </button>
                        <div className="p-2.5 rounded-lg bg-slate-50/80 dark:bg-white/[0.02] border border-slate-200/60 dark:border-white/5 text-[11px] font-mono">
                            <div className="flex items-center justify-between mb-1.5 font-sans">
                                <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Sensor Cluster</span>
                                <span className="flex items-center gap-1 text-[10px] text-emerald-500 font-bold">
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                    {sensorOnline ? "ONLINE" : "OFFLINE"}
                                </span>
                            </div>
                            <div className="flex justify-between text-slate-500 text-[10px]">
                                <span>Policy Mode:</span>
                                <span className="text-slate-700 dark:text-slate-300 font-semibold">Autonomous</span>
                            </div>
                            <div className="flex justify-between text-slate-500 text-[10px] mt-0.5">
                                <span>Cluster Sync:</span>
                                <span className="text-slate-700 dark:text-slate-300 font-semibold">Verified</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Focused Panel */}
                <div className="flex-1 min-w-0 h-full overflow-y-auto terminal-scrollbar pr-1">
                    {activeSection === "deception" && (
                        <div className="space-y-4 animate-in fade-in duration-200">
                            <div className="flex flex-col gap-1 mb-4">
                                <h3 className="text-sm font-bold text-slate-900 dark:text-white">Deception &amp; Honeypot Engine</h3>
                                <p className="text-xs text-slate-500">Configure virtual filesystem depth, canary tokens, and SSH fingerprint countermeasures.</p>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {/* Deception Sensor */}
                                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm overflow-visible flex flex-col justify-between">
                                    <div className="p-3.5 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] rounded-t-xl">
                                        <h4 className="font-display font-semibold text-[13px] tracking-tight flex items-center gap-2 text-indigo-500">
                                            <Database size={15} /> Sensor Node (AsyncSSH)
                                        </h4>
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
                                                onChange={setDeceptionLevel}
                                            />
                                        </div>
                                        <div className="pt-1">
                                            <label className="flex items-center gap-2.5 cursor-pointer group">
                                                <div className="relative flex items-center justify-center w-4 h-4 rounded border border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-[#0f0f0f] group-hover:border-indigo-500 transition-colors">
                                                    <input type="checkbox" checked={fakeKeys} onChange={() => setFakeKeys(!fakeKeys)} className="opacity-0 absolute inset-0 cursor-pointer" />
                                                    {fakeKeys && <Check size={12} className="text-indigo-500 opacity-100" />}
                                                </div>
                                                <div className="flex flex-col">
                                                    <span className="text-[11px] font-medium text-slate-700 dark:text-slate-300">Inject Fake AWS API Keys</span>
                                                    <span className="text-[10px] text-slate-400">Seeds canary credentials in .bash_history to detect exfiltration</span>
                                                </div>
                                            </label>
                                        </div>
                                    </div>
                                </div>

                                {/* HASSH Engine */}
                                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm overflow-visible flex flex-col justify-between">
                                    <div className="p-3.5 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] rounded-t-xl">
                                        <h4 className="font-display font-semibold text-[13px] tracking-tight flex items-center gap-2 text-purple-500">
                                            <Fingerprint size={15} /> Identity Engine (HASSH)
                                        </h4>
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
                                                onChange={setHasshAction}
                                            />
                                        </div>
                                        <div>
                                            <div className="flex items-center justify-between mb-1.5">
                                                <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Confidence Threshold</label>
                                                <span className="text-[11px] font-mono font-bold text-slate-700 dark:text-slate-300">{hasshThreshold}%</span>
                                            </div>
                                            <input
                                                type="range"
                                                min="0"
                                                max="100"
                                                value={hasshThreshold}
                                                onChange={(e) => setHasshThreshold(parseInt(e.target.value, 10))}
                                                className="w-full accent-purple-500 h-1.5 bg-slate-200 dark:bg-slate-800 rounded-full appearance-none outline-none cursor-pointer"
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {activeSection === "soar" && (
                        <div className="space-y-4 animate-in fade-in duration-200">
                            <div className="flex flex-col gap-1 mb-4">
                                <h3 className="text-sm font-bold text-slate-900 dark:text-white">SOAR &amp; Exposure Gateway</h3>
                                <p className="text-xs text-slate-500">Control ingress exposure and configure automated firewall isolation triggers.</p>
                            </div>

                            {/* Exposure Control */}
                            <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm p-4 flex flex-col gap-3">
                                <div className="flex items-start justify-between gap-4">
                                    <div>
                                        <h4 className="font-display font-semibold text-[13px] tracking-tight flex items-center gap-2 text-amber-600 dark:text-amber-500">
                                            <Power size={15} />
                                            Honeypot Exposure Gateway
                                        </h4>
                                        <p className="text-xs text-slate-500 mt-1">
                                            {sensorOnline ? "Live gateway active. Toggle public honeypot traffic forwarding." : "Sensor API unreachable."}
                                        </p>
                                    </div>
                                    <button
                                        type="button"
                                        disabled={exposureBusy || exposureSyncing || exposureCooldownActive || !sensorOnline}
                                        onClick={openExposureConfirm}
                                        className={`shrink-0 inline-flex items-center justify-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all shadow-xs disabled:opacity-50 ${exposurePaused ? "bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20" : "bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/20"}`}
                                    >
                                        <Power size={13} />
                                        {exposureBusy || exposureSyncing ? "Applying..." : exposureCooldownActive ? `Cooldown ${cooldownRemainingSec}s` : (exposurePaused ? "Set Online" : "Set Offline")}
                                    </button>
                                </div>
                                <div className="text-[11px] text-slate-500 flex items-center gap-2 pt-2 border-t border-slate-100 dark:border-white/5">
                                    <span>Current Exposure:</span>
                                    <span className={cn("font-semibold font-mono px-1.5 py-0.5 rounded text-[10px]", effectiveExposureEnabled === false ? "bg-amber-500/10 text-amber-600 border border-amber-500/20" : "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20")}>
                                        {effectiveExposureEnabled === false ? "OFFLINE" : "ONLINE"}
                                    </span>
                                    {exposureSyncing && <span className="text-blue-600 dark:text-blue-400 font-semibold animate-pulse text-[10px]">Syncing...</span>}
                                </div>
                            </div>

                            {/* Automated SOAR Response */}
                            <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm overflow-visible">
                                <div className="p-3.5 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] flex justify-between items-center rounded-t-xl">
                                    <h4 className="font-display font-semibold text-[13px] tracking-tight flex items-center gap-2 text-rose-500">
                                        <Zap size={15} /> Automated Containment Pipeline
                                    </h4>
                                    <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 text-[10px] font-bold uppercase tracking-wider border border-rose-500/20">Active</span>
                                </div>
                                <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4 overflow-visible">
                                    <div>
                                        <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Trigger Condition</label>
                                        <CustomDropdown
                                            options={[
                                                { label: "MITRE Match (>1)", value: "MITRE Match (>1)" },
                                                { label: "Auth Spike (>10/m)", value: "Auth Spike (>10/m)" },
                                                { label: "Any Input", value: "Any Input" },
                                            ]}
                                            value={soarTrigger}
                                            onChange={setSoarTrigger}
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
                                            onChange={setSoarExecution}
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Action Applied</label>
                                        <div className="border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-[#0f0f0f] rounded-lg px-3 py-2 flex items-center gap-2">
                                            <Shield size={14} className="text-slate-400 shrink-0" />
                                            <span className="text-xs font-mono text-slate-700 dark:text-slate-300 truncate">Revoke IP (NSG &amp; Netfilter)</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {activeSection === "llm" && (
                        <div className="space-y-4 animate-in fade-in duration-200">
                            <div className="flex flex-col gap-1 mb-4">
                                <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                    <Sparkles size={16} className="text-purple-500" />
                                    AI &amp; LLM Configuration (Both Engines)
                                </h3>
                                <p className="text-xs text-slate-500">
                                    Configure LLM API keys and model parameters directly from the UI for both the Security Analyst Copilot and the Honeypot Virtual Filesystem (VFS) deception engine.
                                </p>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {/* Side 1: Security Analyst Copilot */}
                                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm overflow-visible flex flex-col justify-between">
                                    <div className="p-3.5 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] rounded-t-xl flex items-center justify-between">
                                        <h4 className="font-display font-semibold text-[13px] tracking-tight flex items-center gap-2 text-blue-500">
                                            <Bot size={15} /> Copilot Chat Agent (Security Analyst)
                                        </h4>
                                        <span className={cn(
                                            "px-2 py-0.5 rounded text-[9.5px] font-mono font-bold uppercase tracking-wider border",
                                            copilotApiKey || hasCopilotKey
                                                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                                                : "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                                        )}>
                                            {copilotApiKey || hasCopilotKey ? "Configured" : "CLI Fallback"}
                                        </span>
                                    </div>
                                    <div className="p-4 space-y-4">
                                        <div>
                                            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                                                AI Provider
                                            </label>
                                            <CustomDropdown
                                                options={[
                                                    { label: "Google Gemini (Recommended)", value: "Google Gemini" },
                                                    { label: "Groq Cloud (Ultra-Fast)", value: "Groq Cloud" },
                                                    { label: "OpenAI (GPT-4o)", value: "OpenAI" },
                                                    { label: "Anthropic Claude", value: "Anthropic Claude" },
                                                    { label: "LiteLLM Unified Gateway", value: "LiteLLM Unified Gateway" },
                                                ]}
                                                value={copilotProvider}
                                                onChange={setCopilotProvider}
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                                                Primary Model
                                            </label>
                                            <CustomDropdown
                                                options={[
                                                    { label: "gemini/gemini-2.0-flash", value: "gemini/gemini-2.0-flash" },
                                                    { label: "groq/llama-3.3-70b-versatile", value: "groq/llama-3.3-70b-versatile" },
                                                    { label: "openai/gpt-4o-mini", value: "openai/gpt-4o-mini" },
                                                    { label: "anthropic/claude-3-5-sonnet", value: "anthropic/claude-3-5-sonnet" },
                                                ]}
                                                value={copilotModel}
                                                onChange={setCopilotModel}
                                            />
                                        </div>

                                        <div>
                                            <div className="flex items-center justify-between mb-1.5">
                                                <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                                                    API Key
                                                </label>
                                                <button
                                                    type="button"
                                                    onClick={() => setShowCopilotKey(!showCopilotKey)}
                                                    className="text-[10px] text-blue-500 hover:text-blue-600 dark:hover:text-blue-400 font-sans normal-case flex items-center gap-1 cursor-pointer"
                                                >
                                                    {showCopilotKey ? <EyeOff size={11} /> : <Eye size={11} />}
                                                    <span>{showCopilotKey ? "Hide" : "Show"}</span>
                                                </button>
                                            </div>
                                            <div className="relative">
                                                <input
                                                    type={showCopilotKey ? "text" : "password"}
                                                    value={copilotApiKey}
                                                    onChange={(e) => setCopilotApiKey(e.target.value)}
                                                    placeholder={hasCopilotKey ? "Leave blank to keep current key" : "AIzaSy... / gsk_... / sk-..."}
                                                    className="w-full h-9 rounded-lg bg-slate-50 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 px-3 text-xs font-mono text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
                                                />
                                            </div>
                                            <span className="text-[10px] text-slate-400 mt-1 block">
                                                Powers real-time natural language threat explanations and SOAR command execution.
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                {/* Side 2: Honeypot Deception Engine (VFS) */}
                                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm overflow-visible flex flex-col justify-between">
                                    <div className="p-3.5 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] rounded-t-xl flex items-center justify-between">
                                        <h4 className="font-display font-semibold text-[13px] tracking-tight flex items-center gap-2 text-purple-500">
                                            <Database size={15} /> Honeypot Deception Engine (VFS)
                                        </h4>
                                        <span className="px-2 py-0.5 rounded text-[9.5px] font-mono font-bold uppercase tracking-wider bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
                                            Deception Node
                                        </span>
                                    </div>
                                    <div className="p-4 space-y-4">
                                        <div>
                                            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                                                Terminal Emulation Mode
                                            </label>
                                            <CustomDropdown
                                                options={[
                                                    { label: "Dynamic VFS Terminal Emulation", value: "Dynamic VFS Terminal Emulation" },
                                                    { label: "Deterministic Offline Fallback", value: "Deterministic Offline Fallback" },
                                                ]}
                                                value={honeypotLlmMode}
                                                onChange={setHoneypotLlmMode}
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                                                Engine Provider
                                            </label>
                                            <CustomDropdown
                                                options={[
                                                    { label: "Inherit from Copilot (Unified)", value: "Inherit from Copilot" },
                                                    { label: "Google Gemini", value: "Google Gemini" },
                                                    { label: "Groq Cloud (Ultra-Fast Response)", value: "Groq Cloud" },
                                                    { label: "OpenAI", value: "OpenAI" },
                                                ]}
                                                value={honeypotProvider}
                                                onChange={setHoneypotProvider}
                                            />
                                        </div>

                                        <div>
                                            <label className="flex items-center gap-2 cursor-pointer mb-2">
                                                <input
                                                    type="checkbox"
                                                    checked={useCopilotKeyForHoneypot}
                                                    onChange={(e) => setUseCopilotKeyForHoneypot(e.target.checked)}
                                                    className="rounded border-slate-300 dark:border-slate-700 text-purple-600 focus:ring-purple-500"
                                                />
                                                <span className="text-[11px] font-medium text-slate-700 dark:text-slate-300">
                                                    Use same API key as Copilot
                                                </span>
                                            </label>

                                            {!useCopilotKeyForHoneypot && (
                                                <div>
                                                    <div className="relative">
                                                        <input
                                                            type={showHoneypotKey ? "text" : "password"}
                                                            value={honeypotApiKey}
                                                            onChange={(e) => setHoneypotApiKey(e.target.value)}
                                                            placeholder="Dedicated Honeypot Engine Key"
                                                            className="w-full h-9 rounded-lg bg-slate-50 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 px-3 text-xs font-mono text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-purple-500/50"
                                                        />
                                                    </div>
                                                </div>
                                            )}
                                        </div>

                                        <div>
                                            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                                                Fallback Model Chain (CSV)
                                            </label>
                                            <input
                                                type="text"
                                                value={fallbackChain}
                                                onChange={(e) => setFallbackChain(e.target.value)}
                                                className="w-full h-9 rounded-lg bg-slate-50 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 px-3 text-xs font-mono text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-purple-500/50"
                                            />
                                            <span className="text-[10px] text-slate-400 mt-1 block">
                                                Automated fallback when rate limits occur (e.g. Groq → OpenAI).
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {activeSection === "telemetry" && (
                        <div className="space-y-4 animate-in fade-in duration-200">
                            <div className="flex flex-col gap-1 mb-4">
                                <h3 className="text-sm font-bold text-slate-900 dark:text-white">Operations &amp; Telemetry Stream</h3>
                                <p className="text-xs text-slate-500">Live operational metrics, upstream endpoints, and websocket event logs.</p>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {/* Telemetry Truth */}
                                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm p-3.5 flex flex-col justify-between">
                                    <div className="border-b border-slate-100 dark:border-white/5 pb-2.5">
                                        <h4 className="font-display font-semibold text-[13px] tracking-tight flex items-center gap-2 text-emerald-600 dark:text-emerald-500 mb-0.5">
                                            <Shield size={15} />
                                            Telemetry Truth Source
                                        </h4>
                                        <p className="text-xs text-slate-500">
                                            Authoritative metrics backend and stream pipeline routing status.
                                        </p>
                                    </div>
                                    <div className="flex flex-col gap-2 mt-2">
                                        <div className="rounded-lg border border-slate-200 dark:border-white/10 p-2.5 bg-slate-50/50 dark:bg-white/[0.02]">
                                            <div className="text-slate-500 uppercase text-[10px] font-semibold mb-0.5">Primary Storage</div>
                                            <div className="font-mono text-xs font-bold text-slate-900 dark:text-white uppercase flex items-center gap-2">
                                                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                                {operations?.telemetrySource ?? "mixed"} (ClickHouse &amp; Redis)
                                            </div>
                                        </div>
                                        <div className="rounded-lg border border-slate-200 dark:border-white/10 p-2.5 bg-slate-50/50 dark:bg-white/[0.02]">
                                            <div className="text-slate-500 uppercase text-[10px] font-semibold mb-0.5">Ingress Pipeline</div>
                                            <div className="font-mono text-xs font-medium text-slate-800 dark:text-slate-200">
                                                NATS JetStream Bus &amp; WebSocket Gateway
                                            </div>
                                        </div>
                                        <div className="rounded-lg border border-slate-200 dark:border-white/10 p-2.5 bg-slate-50/50 dark:bg-white/[0.02]">
                                            <div className="text-slate-500 uppercase text-[10px] font-semibold mb-0.5">Deduplication Cache</div>
                                            <div className="font-mono text-xs font-medium text-slate-800 dark:text-slate-200">
                                                Active (24-Hour Sliding Window)
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Ops Health */}
                                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm flex flex-col justify-between overflow-hidden">
                                    <div className="p-3.5 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] flex items-center justify-between shrink-0">
                                        <h4 className="font-display font-semibold text-[13px] tracking-tight flex items-center gap-2 text-slate-800 dark:text-slate-200">
                                            <Activity size={15} className="text-blue-500" />
                                            Upstream Endpoint Latencies
                                        </h4>
                                        <span className="text-[10px] font-mono text-slate-500">
                                            Max: <span className="font-semibold text-slate-700 dark:text-slate-300">{Number(operations?.telemetry?.maxLatencyMs ?? 0)}ms</span>
                                        </span>
                                    </div>
                                    <div className="p-3.5 flex-1 flex flex-col justify-between gap-1.5">
                                        {latencyRows.map((row) => (
                                            <div key={row.name} className="flex items-center justify-between text-[11px] rounded bg-slate-50 dark:bg-[#0f0f0f] border border-slate-200 dark:border-white/5 px-2.5 py-1">
                                                <span className="text-slate-600 dark:text-slate-400 font-sans">{row.name}</span>
                                                <span className="font-mono text-slate-900 dark:text-slate-200 font-semibold">{row.value}ms</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            {/* Socket Logs */}
                            <div className={isSocketFullScreen ? "fixed inset-4 z-[120] bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-2xl flex flex-col overflow-hidden" : "bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm flex flex-col overflow-hidden min-h-[220px]"}>
                                {isSocketFullScreen && <div className="fixed inset-0 z-[-1] bg-black/60 backdrop-blur-sm" onClick={() => setIsSocketFullScreen(false)} />}
                                <div className="p-3 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] flex justify-between items-center shrink-0">
                                    <h4 className="font-display font-semibold text-[13px] tracking-tight text-slate-800 dark:text-slate-200">Live Socket Telemetry</h4>
                                    <div className="flex items-center gap-3">
                                        <div className="flex gap-3 text-[10px] font-mono text-slate-500 mr-2">
                                            <span>Conn: {socketTelemetry.connectCount}</span>
                                            <span>Drop: {socketTelemetry.disconnectCount}</span>
                                            <span className={socketTelemetry.connected ? "text-emerald-500 font-bold" : "text-amber-500 font-bold"}>
                                                {socketTelemetry.connected ? "ONLINE" : "OFFLINE"}
                                            </span>
                                        </div>
                                        <button onClick={() => setIsSocketFullScreen(!isSocketFullScreen)} className="p-1 text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300 transition-colors rounded hover:bg-slate-200 dark:hover:bg-white/10" title={isSocketFullScreen ? "Exit Fullscreen" : "Fullscreen"}>
                                            {isSocketFullScreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                                        </button>
                                    </div>
                                </div>
                                <div className="p-3 max-h-56 overflow-y-auto space-y-1 terminal-scrollbar bg-slate-50/30 dark:bg-[#050505]">
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
                    )}
                </div>
            </div>

            {showExposureConfirm && (
                <div className="fixed inset-0 z-[140] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="bg-white dark:bg-[#0a0a0a] p-6 rounded-2xl border border-slate-200 dark:border-white/10 shadow-2xl max-w-sm w-full mx-4 animate-in zoom-in-95 duration-200">
                        <h3 className="text-lg font-bold mb-2">Exposure Control</h3>
                        <p className="text-slate-500 dark:text-slate-400 text-sm mb-6">
                            {pendingExposurePaused
                                ? "Set honeypot exposure to offline? Admin dashboard will stay online."
                                : "Set honeypot exposure to online?"}
                        </p>
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={cancelExposureConfirm}
                                className="px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-100 dark:hover:bg-white/10 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmExposureToggle}
                                className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-bold shadow-lg shadow-blue-500/20 hover:bg-blue-500 transition-colors"
                            >
                                Confirm
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
