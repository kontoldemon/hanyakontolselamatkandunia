"use client";

import { Power, X } from "lucide-react";
import { useState, useCallback, useEffect, useRef } from "react";
import { useSensorOperations, useWarRoomState } from "@/lib/liveEvents";
import { useAgentCommand } from "@/lib/AgentContext";
import { useExposureControl } from "@/components/settings/useExposureControl";
import DeceptionSection from "@/components/settings/DeceptionSection";
import SoarExposureSection from "@/components/settings/SoarExposureSection";
import AiEnginesSection from "@/components/settings/AiEnginesSection";
import MobileAlertsPanel from "@/components/settings/MobileAlertsPanel";
import ScrollDownHint from "@/components/ui/ScrollDownHint";
import { cn } from "@/lib/utils";

const DECEPTION_LEVELS: Record<string, string> = {
    "high (full vfs)": "full",
    high: "full",
    full: "full",
    "medium (restricted)": "restricted",
    medium: "restricted",
    restricted: "restricted",
    "low (port listener)": "listener",
    low: "listener",
    listener: "listener",
};

const HASSH_ACTIONS: Record<string, string> = {
    "immediate drop": "drop",
    drop: "drop",
    "allow & monitor": "monitor",
    monitor: "monitor",
};

const SOAR_TRIGGERS: Record<string, string> = {
    "risk score (>= threshold)": "risk",
    "risk score": "risk",
    risk: "risk",
    "mitre match (>1)": "mitre",
    mitre: "mitre",
    "auth spike (>10/m)": "auth_spike",
    "auth spike": "auth_spike",
    spike: "auth_spike",
    "any input": "any_input",
    any: "any_input",
};

const SOAR_EXECUTIONS: Record<string, string> = {
    "azure function (event grid)": "eventgrid",
    "event grid": "eventgrid",
    eventgrid: "eventgrid",
    "host netfilter daemon": "host",
    netfilter: "host",
    host: "host",
};

function normalizeChoice(map: Record<string, string>, value: string, fallback: string): string {
    return map[value.trim().toLowerCase()] ?? fallback;
}

export default function SettingsPage() {
    const operations = useSensorOperations();
    const warRoom = useWarRoomState();
    const [savedToast, setSavedToast] = useState<string | boolean>(false);

    // Deception State
    const [deceptionLevel, setDeceptionLevel] = useState("full");
    const [hasshAction, setHasshAction] = useState("monitor");
    const [hasshThreshold, setHasshThreshold] = useState(85);
    const [fakeKeys, setFakeKeys] = useState(true);

    // SOAR State
    const [soarTrigger, setSoarTrigger] = useState("risk");
    const [soarExecution, setSoarExecution] = useState("host");

    // AI & LLM Engine State
    const [copilotProvider, setCopilotProvider] = useState("gemini");
    const [copilotModel, setCopilotModel] = useState("gemini/gemini-2.0-flash");
    const [copilotApiKey, setCopilotApiKey] = useState("");
    const [hasCopilotKey, setHasCopilotKey] = useState(false);
    const [showCopilotKey, setShowCopilotKey] = useState(false);

    const [honeypotLlmMode, setHoneypotLlmMode] = useState("dynamic");
    const [fallbackChain, setFallbackChain] = useState("groq/llama-3.3-70b-versatile, openai/gpt-4o-mini");
    const [hourlyLimit, setHourlyLimit] = useState(200);
    const [promptSanitization, setPromptSanitization] = useState(true);

    const [configLoaded, setConfigLoaded] = useState(false);
    const toastTimer = useRef<number | null>(null);

    const notify = useCallback((message: string) => {
        setSavedToast(message);
        if (toastTimer.current !== null) {
            window.clearTimeout(toastTimer.current);
        }
        toastTimer.current = window.setTimeout(() => setSavedToast(false), 3000);
    }, []);

    useEffect(() => {
        return () => {
            if (toastTimer.current !== null) {
                window.clearTimeout(toastTimer.current);
            }
        };
    }, []);

    useEffect(() => {
        let cancelled = false;
        async function loadConfig() {
            const [runtimePayload, llmPayload] = await Promise.all([
                fetch("/api/cloudsentinel/runtime-config", { cache: "no-store" })
                    .then((res) => res.json())
                    .catch(() => null),
                fetch("/api/cloudsentinel/llm-config", { cache: "no-store" })
                    .then((res) => res.json())
                    .catch(() => null),
            ]);
            if (cancelled) return;

            if (runtimePayload?.ok && runtimePayload.config) {
                const config = runtimePayload.config;
                if (config.deception?.level) setDeceptionLevel(config.deception.level);
                if (typeof config.deception?.seed_canary_keys === "boolean") setFakeKeys(config.deception.seed_canary_keys);
                if (config.hassh?.action) setHasshAction(config.hassh.action);
                if (typeof config.hassh?.threshold === "number") setHasshThreshold(config.hassh.threshold);
                if (config.soar?.trigger) setSoarTrigger(config.soar.trigger);
                if (config.soar?.execution) setSoarExecution(config.soar.execution);
            }

            if (llmPayload?.ok) {
                if (llmPayload.provider) setCopilotProvider(llmPayload.provider);
                if (llmPayload.model) setCopilotModel(llmPayload.model);
                setHasCopilotKey(Boolean(llmPayload.has_api_key));
                if (Array.isArray(llmPayload.fallback_models)) setFallbackChain(llmPayload.fallback_models.join(", "));
                if (typeof llmPayload.hourly_limit === "number") setHourlyLimit(llmPayload.hourly_limit);
                if (typeof llmPayload.prompt_sanitization === "boolean") setPromptSanitization(llmPayload.prompt_sanitization);
                if (llmPayload.deception_mode) setHoneypotLlmMode(llmPayload.deception_mode);
            }

            setConfigLoaded(true);
        }
        loadConfig();
        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        if (!configLoaded) return;
        const timer = window.setTimeout(async () => {
            try {
                const response = await fetch("/api/cloudsentinel/runtime-config", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        deception: { level: deceptionLevel, seed_canary_keys: fakeKeys },
                        hassh: { action: hasshAction, threshold: hasshThreshold },
                        soar: { trigger: soarTrigger, execution: soarExecution },
                    }),
                });
                const data = await response.json().catch(() => ({}));
                if (!data.ok) {
                    notify(`Save failed: ${data.error ?? "sensor unreachable"}`);
                }
            } catch {
                notify("Save failed: sensor unreachable");
            }
        }, 600);
        return () => window.clearTimeout(timer);
    }, [configLoaded, deceptionLevel, fakeKeys, hasshAction, hasshThreshold, soarTrigger, soarExecution, notify]);

    useEffect(() => {
        if (!configLoaded) return;
        const timer = window.setTimeout(async () => {
            const submittedCopilotKey = copilotApiKey.trim();
            try {
                const response = await fetch("/api/cloudsentinel/llm-config", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        provider: copilotProvider,
                        model: copilotModel,
                        ...(submittedCopilotKey ? { api_key: submittedCopilotKey } : {}),
                        fallback_models: fallbackChain.split(",").map((part) => part.trim()).filter(Boolean),
                        hourly_limit: hourlyLimit,
                        prompt_sanitization: promptSanitization,
                        deception_mode: honeypotLlmMode,
                    }),
                });
                const data = await response.json().catch(() => ({}));
                if (data.ok) {
                    if (submittedCopilotKey) {
                        setCopilotApiKey("");
                        setHasCopilotKey(true);
                    }
                } else {
                    notify(`Save failed: ${data.error ?? "sensor unreachable"}`);
                }
            } catch {
                notify("Save failed: sensor unreachable");
            }
        }, 600);
        return () => window.clearTimeout(timer);
    }, [configLoaded, copilotProvider, copilotModel, copilotApiKey, honeypotLlmMode, fallbackChain, hourlyLimit, promptSanitization, notify]);

    useAgentCommand("settings.deception_level", useCallback((v: string) => setDeceptionLevel(normalizeChoice(DECEPTION_LEVELS, v, "full")), []));
    useAgentCommand("settings.hassh_action", useCallback((v: string) => setHasshAction(normalizeChoice(HASSH_ACTIONS, v, "monitor")), []));
    useAgentCommand("settings.hassh_threshold", useCallback((v: string) => setHasshThreshold(Math.max(0, Math.min(100, parseInt(v, 10) || 85))), []));
    useAgentCommand("settings.fake_keys", useCallback((v: string) => setFakeKeys((previous) => (v === "toggle" ? !previous : v === "true" || v === "on")), []));
    useAgentCommand("settings.soar_trigger", useCallback((v: string) => setSoarTrigger(normalizeChoice(SOAR_TRIGGERS, v, "risk")), []));
    useAgentCommand("settings.soar_execution", useCallback((v: string) => setSoarExecution(normalizeChoice(SOAR_EXECUTIONS, v, "host")), []));

    const scrollRef = useRef<HTMLDivElement>(null);
    const [showScrollDown, setShowScrollDown] = useState(false);

    const handleScroll = useCallback(() => {
        if (!scrollRef.current) return;
        const el = scrollRef.current;
        const dist = el.scrollHeight - (el.scrollTop + el.clientHeight);
        setShowScrollDown(dist > 35);
    }, []);

    const scrollToNext = useCallback(() => {
        if (!scrollRef.current) return;
        scrollRef.current.scrollBy({
            top: 350,
            behavior: "smooth",
        });
    }, []);

    useEffect(() => {
        const timer = setTimeout(() => {
            if (!scrollRef.current) return;
            const el = scrollRef.current;
            setShowScrollDown(el.scrollHeight - el.clientHeight > 35);
        }, 150);
        return () => clearTimeout(timer);
    }, []);

    const {
        exposurePaused,
        exposureBusy,
        toast,
        showExposureConfirm,
        isClosingExposureConfirm,
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

    return (
        <div className="h-full flex flex-col overflow-hidden relative">
            {(toast || savedToast) && (
                <div className="fixed top-16 md:top-5 left-1/2 -translate-x-1/2 z-[160] max-w-[calc(100vw-2rem)] px-4 py-2 rounded-lg border shadow-lg text-xs font-semibold text-center bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-400 backdrop-blur-md animate-in fade-in slide-in-from-top-2 duration-200">
                    {typeof savedToast === "string"
                        ? savedToast
                        : savedToast
                            ? "Configuration updated and synchronized."
                            : toast?.message}
                </div>
            )}

            {/* Scrollable Single Page Vertical Listing - Decoupled & Full Width */}
            <div ref={scrollRef} onScroll={handleScroll} className="flex-1 min-h-0 overflow-y-auto terminal-scrollbar pr-1 pt-1">
                <div className="max-w-4xl mx-auto space-y-3.5 pb-1">
                    {/* 1. SOAR & INGRESS EXPOSURE CONTROL */}
                    <SoarExposureSection
                        soarTrigger={soarTrigger}
                        setSoarTrigger={setSoarTrigger}
                        soarExecution={soarExecution}
                        setSoarExecution={setSoarExecution}
                        exposurePaused={exposurePaused}
                        exposureBusy={exposureBusy}
                        exposureSyncing={exposureSyncing}
                        exposureCooldownActive={exposureCooldownActive}
                        cooldownRemainingSec={cooldownRemainingSec}
                        sensorOnline={sensorOnline}
                        effectiveExposureEnabled={effectiveExposureEnabled}
                        openExposureConfirm={openExposureConfirm}
                    />

                    {/* 2. DECEPTION ENGINE */}
                    <DeceptionSection
                        deceptionLevel={deceptionLevel}
                        setDeceptionLevel={setDeceptionLevel}
                        fakeKeys={fakeKeys}
                        setFakeKeys={setFakeKeys}
                        hasshAction={hasshAction}
                        setHasshAction={setHasshAction}
                        hasshThreshold={hasshThreshold}
                        setHasshThreshold={setHasshThreshold}
                    />

                    {/* 3. AI & LLM ENGINES */}
                    <AiEnginesSection
                        copilotProvider={copilotProvider}
                        setCopilotProvider={setCopilotProvider}
                        copilotModel={copilotModel}
                        setCopilotModel={setCopilotModel}
                        copilotApiKey={copilotApiKey}
                        setCopilotApiKey={setCopilotApiKey}
                        hasCopilotKey={hasCopilotKey}
                        showCopilotKey={showCopilotKey}
                        setShowCopilotKey={setShowCopilotKey}
                        honeypotLlmMode={honeypotLlmMode}
                        setHoneypotLlmMode={setHoneypotLlmMode}
                        fallbackChain={fallbackChain}
                        setFallbackChain={setFallbackChain}
                        hourlyLimit={hourlyLimit}
                        setHourlyLimit={setHourlyLimit}
                        promptSanitization={promptSanitization}
                        setPromptSanitization={setPromptSanitization}
                    />

                    {/* 4. MOBILE ALERTS */}
                    <section id="sec-mobile" className="space-y-3.5 scroll-mt-2 animate-in fade-in duration-150">
                        <MobileAlertsPanel
                            onNotify={(msg) => {
                                setSavedToast(msg);
                                setTimeout(() => setSavedToast(false), 3000);
                            }}
                        />
                    </section>
                </div>
            </div>

            <ScrollDownHint visible={showScrollDown} onScrollDown={scrollToNext} />

            {/* Confirmation Modal */}
            {showExposureConfirm && (
                <div
                    onClick={cancelExposureConfirm}
                    className={cn(
                        "fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-md p-4",
                        isClosingExposureConfirm ? "animate-overlay-out" : "animate-overlay-in"
                    )}
                >
                    <div
                        onClick={(e) => e.stopPropagation()}
                        className={cn(
                            "relative max-w-[320px] w-full overflow-hidden rounded-3xl border border-slate-200/80 bg-white/95 p-6 text-center shadow-2xl backdrop-blur-2xl dark:border-white/10 dark:bg-[#0c0c0e] dark:shadow-[0_24px_60px_rgba(0,0,0,0.8)]",
                            isClosingExposureConfirm ? "animate-modal-out" : "animate-modal-in"
                        )}
                    >
                        <button
                            type="button"
                            onClick={cancelExposureConfirm}
                            className="absolute top-4 right-4 flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition cursor-pointer"
                            aria-label="Close"
                        >
                            <X size={15} />
                        </button>

                        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200/80 bg-slate-100/80 text-slate-700 shadow-sm dark:border-white/10 dark:bg-white/[0.05] dark:text-slate-200">
                            <Power size={16} className={pendingExposurePaused ? "text-amber-500" : "text-emerald-500"} />
                        </div>

                        <h3 className="font-display text-base font-bold tracking-tight text-slate-900 sm:text-lg dark:text-white">
                            {pendingExposurePaused ? "Set Ingress Offline" : "Set Ingress Online"}
                        </h3>
                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                            {pendingExposurePaused
                                ? "Toggling honeypot exposure offline detaches public IP forwarding rules immediately. Admin dashboard will stay online."
                                : "Set honeypot ingress to online to resume public traffic capture."}
                        </p>

                        <div className="mt-5 flex items-center gap-2.5">
                            <button
                                type="button"
                                onClick={cancelExposureConfirm}
                                className="inline-flex h-11 flex-1 items-center justify-center rounded-full border border-slate-200/80 bg-white/80 dark:border-white/10 dark:bg-white/[0.04] text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.08] transition active:scale-95 cursor-pointer"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={confirmExposureToggle}
                                className={cn(
                                    "inline-flex h-11 flex-1 items-center justify-center gap-1.5 rounded-full px-4 text-xs font-semibold text-white shadow-sm transition active:scale-95 cursor-pointer",
                                    pendingExposurePaused ? "bg-amber-600 hover:bg-amber-500" : "bg-emerald-600 hover:bg-emerald-500"
                                )}
                            >
                                <Power size={12} />
                                <span>Confirm</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
