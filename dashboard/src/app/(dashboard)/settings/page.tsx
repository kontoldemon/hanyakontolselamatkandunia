"use client";

import { Shield, Zap, Fingerprint, Database, Save, Activity, Check, Power, Maximize2, Minimize2 } from "lucide-react";
import { useState, useCallback, useEffect } from "react";
import { useSensorOperations, useSocketTelemetry, useWarRoomState } from "@/lib/liveEvents";
import { useAgentCommand } from "@/lib/AgentContext";

import CustomDropdown from "@/components/CustomDropdown";
const EXPOSURE_STATE_KEY = "cloudsentinel.exposure.paused";

export default function SettingsPage() {
    const operations = useSensorOperations();
    const socketTelemetry = useSocketTelemetry();
    const warRoom = useWarRoomState();
    const [exposurePaused, setExposurePaused] = useState(() => {
        if (typeof window === "undefined") return false;
        return window.sessionStorage.getItem(EXPOSURE_STATE_KEY) === "1";
    });
    const [exposureBusy, setExposureBusy] = useState(false);
    const [isSocketFullScreen, setIsSocketFullScreen] = useState(false);
    const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);
    const [showExposureConfirm, setShowExposureConfirm] = useState(false);
    const [pendingExposurePaused, setPendingExposurePaused] = useState<boolean | null>(null);
    const [pendingEffectiveExposurePaused, setPendingEffectiveExposurePaused] = useState<boolean | null>(null);
    const [syncStartedAt, setSyncStartedAt] = useState<number | null>(null);
    const [exposureCooldownUntil, setExposureCooldownUntil] = useState<number>(0);
    const [cooldownNow, setCooldownNow] = useState<number>(() => Date.now());
    // Controlled state for all config dropdowns
    const [deceptionLevel, setDeceptionLevel] = useState("High (Full VFS)");
    const [hasshAction, setHashAction] = useState("Immediate Drop");
    const [hasshThreshold, setHashThreshold] = useState(85);
    const [fakeKeys, setFakeKeys] = useState(true);
    const [soarTrigger, setSoarTrigger] = useState("MITRE Match (>1)");
    const [soarExecution, setSoarExecution] = useState("Lambda (Warm)");

    // ── Agent command handlers ──
    useAgentCommand("settings.deception_level", useCallback((v: string) => setDeceptionLevel(v), []));
    useAgentCommand("settings.hassh_action", useCallback((v: string) => setHashAction(v), []));
    useAgentCommand("settings.hassh_threshold", useCallback((v: string) => setHashThreshold(Math.max(0, Math.min(100, parseInt(v) || 85))), []));
    useAgentCommand("settings.fake_keys", useCallback((v: string) => setFakeKeys(v === "true" || v === "toggle" ? !fakeKeys : v === "on"), [fakeKeys]));
    useAgentCommand("settings.soar_trigger", useCallback((v: string) => setSoarTrigger(v), []));
    useAgentCommand("settings.soar_execution", useCallback((v: string) => setSoarExecution(v), []));
    useAgentCommand("socket.fullscreen", useCallback(() => setIsSocketFullScreen((p) => !p), []));
    const upstreamLatency = operations?.telemetry?.upstreamLatencyMs ?? {};
    const sensorOnline = operations?.source === "live" || operations?.sensor.readiness.ok === true;
    const exposureSyncing = warRoom.exposure?.syncing === true;
    const effectiveExposureEnabled = warRoom.exposure?.effectiveEnabled;
    const cooldownRemainingSec = Math.max(0, Math.ceil((exposureCooldownUntil - cooldownNow) / 1000));
    const exposureCooldownActive = cooldownRemainingSec > 0;
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

    async function applyExposure(nextPaused: boolean) {
        setExposureBusy(true);
        setSyncStartedAt(Date.now());
        setPendingEffectiveExposurePaused(nextPaused);
        try {
            const response = await fetch("/api/cloudsentinel/exposure", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ enabled: !nextPaused }),
            });
            const data = await response.json();
            const hasPausedState = typeof data.paused === "boolean";
            if (hasPausedState) {
                const paused = Boolean(data.paused);
                setExposurePaused(paused);
                if (typeof window !== "undefined") {
                    window.sessionStorage.setItem(EXPOSURE_STATE_KEY, paused ? "1" : "0");
                }
            }
            if (data.ok) {
                const paused = hasPausedState ? Boolean(data.paused) : nextPaused;
                setToast({
                    message: paused ? "Applying offline state..." : "Applying online state...",
                    type: "info",
                });
            } else {
                if (data.error === "cooldown_active") {
                    const remainingMs = Number(data.cooldownRemainingMs ?? 0);
                    if (Number.isFinite(remainingMs) && remainingMs > 0) {
                        setExposureCooldownUntil(Date.now() + remainingMs);
                    }
                    setExposureBusy(false);
                    setPendingEffectiveExposurePaused(null);
                    setToast({
                        message: `Exposure cooldown active. Try again in ${Math.max(1, Math.ceil(remainingMs / 1000))}s.`,
                        type: "info",
                    });
                    return;
                }
                if (hasPausedState) {
                    const paused = Boolean(data.paused);
                    setExposureBusy(false);
                    setPendingEffectiveExposurePaused(null);
                    setToast({
                        message: paused
                            ? "Exposure switched to offline with partial backend warning."
                            : "Exposure switched to online with partial backend warning.",
                        type: "info",
                    });
                } else {
                    setExposureBusy(false);
                    setPendingEffectiveExposurePaused(null);
                    setToast({ message: data.error ?? "Exposure update failed.", type: "error" });
                }
            }
        } catch {
            setExposureBusy(false);
            setPendingEffectiveExposurePaused(null);
            setToast({ message: "Exposure update failed.", type: "error" });
        }
    }

    function openExposureConfirm() {
        if (exposureBusy || exposureSyncing || exposureCooldownActive || !sensorOnline) return;
        setPendingExposurePaused(!exposurePaused);
        setShowExposureConfirm(true);
    }

    async function confirmExposureToggle() {
        if (pendingExposurePaused === null) {
            setShowExposureConfirm(false);
            return;
        }
        setShowExposureConfirm(false);
        await applyExposure(pendingExposurePaused);
        setPendingExposurePaused(null);
    }

    useEffect(() => {
        if (!toast) return;
        const timer = window.setTimeout(() => setToast(null), 2500);
        return () => window.clearTimeout(timer);
    }, [toast]);

    useEffect(() => {
        const timer = window.setInterval(() => setCooldownNow(Date.now()), 500);
        return () => window.clearInterval(timer);
    }, []);

    useEffect(() => {
        if (!exposureSyncing) {
            return;
        }
        if (!syncStartedAt) {
            return;
        }
        const timer = window.setInterval(() => {
            const elapsed = Date.now() - syncStartedAt;
            if (elapsed < 8000) {
                return;
            }
            setToast({
                message: "Exposure sync taking too long. Keeping last effective state.",
                type: "error",
            });
            if (typeof effectiveExposureEnabled === "boolean") {
                const paused = !effectiveExposureEnabled;
                setExposurePaused(paused);
                if (typeof window !== "undefined") {
                    window.sessionStorage.setItem(EXPOSURE_STATE_KEY, paused ? "1" : "0");
                }
            }
            setExposureBusy(false);
            setPendingEffectiveExposurePaused(null);
            setSyncStartedAt(null);
        }, 400);
        return () => window.clearInterval(timer);
    }, [exposureSyncing, syncStartedAt, effectiveExposureEnabled]);

    useEffect(() => {
        if (pendingEffectiveExposurePaused === null) {
            return;
        }
        if (typeof effectiveExposureEnabled !== "boolean") {
            return;
        }
        if (exposureSyncing) {
            return;
        }
        const effectivePaused = !effectiveExposureEnabled;
        if (effectivePaused !== pendingEffectiveExposurePaused) {
            return;
        }
        const timer = window.setTimeout(() => {
            setExposurePaused(effectivePaused);
            if (typeof window !== "undefined") {
                window.sessionStorage.setItem(EXPOSURE_STATE_KEY, effectivePaused ? "1" : "0");
            }
            setExposureCooldownUntil(Date.now() + 8000);
            setExposureBusy(false);
            setPendingEffectiveExposurePaused(null);
            setSyncStartedAt(null);
            setToast({
                message: effectivePaused ? "Honeypot exposure set to offline." : "Honeypot exposure set to online.",
                type: "success",
            });
        }, 0);
        return () => window.clearTimeout(timer);
    }, [pendingEffectiveExposurePaused, effectiveExposureEnabled, exposureSyncing]);

    return (
        <div className="h-full flex flex-col gap-6">
            {toast && (
                <div className={`fixed top-5 left-1/2 -translate-x-1/2 z-[160] px-3 py-2 rounded-lg border shadow-lg text-xs font-semibold ${
                    toast.type === "success"
                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-400"
                        : toast.type === "error"
                            ? "bg-red-500/10 border-red-500/30 text-red-700 dark:text-red-400"
                            : "bg-slate-500/10 border-slate-500/30 text-slate-700 dark:text-slate-300"
                }`}>
                    {toast.message}
                </div>
            )}
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

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0 overflow-hidden pr-1">
                
                {/* Left Column: Telemetry & Controls */}
                <div className="space-y-6 flex flex-col min-h-0">
                    <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm p-4 flex flex-col gap-3">
                        <h3 className="font-semibold text-sm flex items-center gap-2 text-emerald-600 dark:text-emerald-500">
                            <Shield size={16} />
                            Telemetry Truth
                        </h3>
                        <div className="grid grid-cols-1 gap-2 text-[11px]">
                            <div className="rounded border border-slate-200 dark:border-white/10 p-2">
                                <div className="text-slate-500 uppercase text-[10px]">Primary Source</div>
                                <div className="font-bold text-slate-700 dark:text-slate-300">{operations?.telemetrySource ?? "mixed"}</div>
                            </div>
                        </div>
                    </div>

                    <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm p-4 flex flex-col gap-3">
                        <div className="flex items-start justify-between gap-4">
                            <div>
                                <h3 className="font-semibold text-sm flex items-center gap-2 text-amber-600 dark:text-amber-500">
                                    <Power size={16} />
                                    Exposure Control
                                </h3>
                                <p className="text-[10px] text-slate-500 mt-1">
                                    {sensorOnline ? "Admin API connected. Toggle public honeypot traffic." : "Sensor API unreachable."}
                                </p>
                            </div>
                            <button
                                type="button"
                                disabled={exposureBusy || exposureSyncing || exposureCooldownActive || !sensorOnline}
                                onClick={openExposureConfirm}
                                className={`shrink-0 inline-flex items-center justify-center gap-1.5 rounded px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider transition-colors disabled:opacity-50 ${exposurePaused ? "bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 border border-emerald-500/20" : "bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 border border-amber-500/20"}`}
                            >
                                <Power size={12} />
                                {exposureBusy || exposureSyncing ? "Applying..." : exposureCooldownActive ? `Cooldown ${cooldownRemainingSec}s` : (exposurePaused ? "Offline" : "Online")}
                            </button>
                        </div>
                        <div className="text-[10px] text-slate-500">
                            Effective: <span className="font-semibold text-slate-700 dark:text-slate-300">{effectiveExposureEnabled === false ? "Offline" : "Online"}</span>
                            {exposureSyncing ? <span className="ml-2 text-blue-600 dark:text-blue-400 font-semibold">Syncing...</span> : null}
                        </div>
                    </div>

                    <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm flex-1 min-h-0 flex flex-col overflow-hidden">
                        <div className="p-4 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] shrink-0">
                            <h3 className="font-semibold text-sm flex items-center gap-2 text-slate-800 dark:text-slate-200">
                                <Activity size={16} className="text-blue-500" />
                                Ops Health
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
                <div className="lg:col-span-2 space-y-6 flex flex-col min-h-0">
                    
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
                                        options={[
                                            { label: "High (Full VFS)", value: "High (Full VFS)" },
                                            { label: "Medium (Restricted)", value: "Medium (Restricted)" },
                                            { label: "Low (Port listener)", value: "Low (Port listener)" }
                                        ]}
                                        value={deceptionLevel}
                                        onChange={setDeceptionLevel}
                                    />
                                </div>
                                <div className="pt-2">
                                    <label className="flex items-center gap-2 cursor-pointer group">
                                        <div className="relative flex items-center justify-center w-4 h-4 rounded border border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-[#0f0f0f] group-hover:border-indigo-500 transition-colors">
                                            <input type="checkbox" checked={fakeKeys} onChange={() => setFakeKeys(!fakeKeys)} className="opacity-0 absolute inset-0 cursor-pointer" />
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
                                <h3 className="font-semibold text-sm flex items-center gap-2 text-purple-500">
                                    <Fingerprint size={16} /> Identity Engine (HASSH)
                                </h3>
                            </div>
                            <div className="p-4 space-y-4">
                                <div>
                                    <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Malicious HASSH Action</label>
                                    <CustomDropdown 
                                        options={[
                                            { label: "Immediate Drop", value: "Immediate Drop" },
                                            { label: "Allow & Monitor", value: "Allow & Monitor" },
                                            { label: "Tarpit", value: "Tarpit" }
                                        ]}
                                        value={hasshAction}
                                        onChange={setHashAction}
                                    />
                                </div>
                                <div>
                                    <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Confidence Threshold</label>
                                    <div className="flex items-center gap-3">
                                        <input type="range" min="0" max="100" value={hasshThreshold} onChange={(e) => setHashThreshold(parseInt(e.target.value))} className="flex-1 accent-purple-500 h-1 bg-slate-200 dark:bg-slate-800 rounded-full appearance-none outline-none" />
                                        <span className="text-[11px] font-mono font-bold w-8 text-right text-slate-700 dark:text-slate-300">{hasshThreshold}%</span>
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
                                <CustomDropdown options={[
                                    { label: "MITRE Match (>1)", value: "MITRE Match (>1)" },
                                    { label: "Auth Spike (>10/m)", value: "Auth Spike (>10/m)" },
                                    { label: "Any Input", value: "Any Input" }
                                ]} value={soarTrigger} onChange={setSoarTrigger} />
                            </div>
                            <div>
                                <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Execution Path</label>
                                <CustomDropdown options={[
                                    { label: "Lambda (Warm)", value: "Lambda (Warm)" },
                                    { label: "Lambda (Cold)", value: "Lambda (Cold)" },
                                    { label: "Local Docker", value: "Local Docker" }
                                ]} value={soarExecution} onChange={setSoarExecution} />
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
                        {isSocketFullScreen && <div className="fixed inset-0 z-[-1] bg-black/60 backdrop-blur-sm" onClick={() => setIsSocketFullScreen(false)} />}
                        <div className="p-3 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] flex justify-between items-center shrink-0">
                            <h3 className="font-semibold text-sm text-slate-800 dark:text-slate-200">Socket Telemetry</h3>
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
                                onClick={() => {
                                    setShowExposureConfirm(false);
                                    setPendingExposurePaused(null);
                                    setToast({ message: "Exposure update cancelled.", type: "info" });
                                }}
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
