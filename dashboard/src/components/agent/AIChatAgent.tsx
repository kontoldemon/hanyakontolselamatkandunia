"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { Sparkles, Send, X, Loader2 } from "lucide-react";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useCapturedSessions, useDashboardStats, useLiveThreatLogs, useSensorOperations } from "@/lib/liveEvents";
import { useIntelStats } from "@/lib/intelStats";
import { useAgent } from "@/lib/AgentContext";
import type { AgentMessage } from "@/lib/agentActions";
import { parseActionsFromResponse, detectIntentActions } from "@/lib/agentActions";
import {
    buildAgentPromptContext,
    buildIntelligenceFactsJson,
    computeIntelligenceSnapshot,
} from "./buildAgentPromptContext";
import AgentMessageList, { buildOfflineFallbackMessage } from "./AgentMessageList";

export default function AIChatAgent() {
    const [isOpen, setIsOpen] = useState(false);
    const [hasUnread, setHasUnread] = useState(false);
    const [messages, setMessages] = useState<AgentMessage[]>([
        {
            role: "ai",
            content: "Hi! I'm CloudSentinel AI. I can explain threats, navigate to attackers, block IPs, and control the dashboard for you. What would you like to do?",
        },
    ]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const panelRef = useRef<HTMLDivElement>(null);
    const messagesRef = useRef<AgentMessage[]>(messages);
    const pathname = usePathname();
    const { executeAction, isExecuting } = useAgent();
    const lastAiMsgCountRef = useRef(1);

    const stats = useDashboardStats();
    const sessions = useCapturedSessions();
    const liveLogs = useLiveThreatLogs();
    const operations = useSensorOperations();
    const intelStats = useIntelStats(liveLogs, sessions);
    const activeIpCount = sessions.filter((s) => (s.status ?? "").toLowerCase() === "active").length;

    const topIps = sessions.slice(0, 8).map((s) => `${s.ip} (${s.country}, ${s.status})`).join(", ");

    const intelligenceSnapshot = useMemo(
        () => computeIntelligenceSnapshot(liveLogs, sessions, operations, stats, intelStats),
        [liveLogs, sessions, operations, stats, intelStats],
    );

    const intelligenceFactsJson = useMemo(
        () => buildIntelligenceFactsJson(intelStats, sessions, liveLogs, intelligenceSnapshot),
        [intelStats, sessions, liveLogs, intelligenceSnapshot],
    );

    const [focusIp, setFocusIp] = useState("");
    useEffect(() => {
        let timer: ReturnType<typeof setTimeout> | null = null;
        const updateFocusIp = () => {
            if (timer) clearTimeout(timer);
            timer = setTimeout(() => {
                const params = new URLSearchParams(window.location.search);
                const next = params.get("focusIp")?.trim() ?? "";
                setFocusIp((prev) => (prev === next ? prev : next));
            }, 0);
        };
        const patchHistoryForLocationChange = () => {
            const historyAny = window.history as History & { __cloudsentinelPatched?: boolean };
            if (historyAny.__cloudsentinelPatched) return;
            const wrap = (method: "pushState" | "replaceState") => {
                const original = window.history[method];
                window.history[method] = function (...args: Parameters<History[typeof method]>) {
                    const result = original.apply(this, args);
                    setTimeout(() => {
                        window.dispatchEvent(new Event("locationchange"));
                    }, 0);
                    return result;
                };
            };
            wrap("pushState");
            wrap("replaceState");
            historyAny.__cloudsentinelPatched = true;
        };
        patchHistoryForLocationChange();
        updateFocusIp();
        window.addEventListener("popstate", updateFocusIp);
        window.addEventListener("hashchange", updateFocusIp);
        window.addEventListener("locationchange", updateFocusIp);
        return () => {
            if (timer) clearTimeout(timer);
            window.removeEventListener("popstate", updateFocusIp);
            window.removeEventListener("hashchange", updateFocusIp);
            window.removeEventListener("locationchange", updateFocusIp);
        };
    }, [pathname]);
    const focusedSession = focusIp ? sessions.find((s) => s.ip === focusIp) : null;

    useEffect(() => {
        messagesRef.current = messages;
    }, [messages]);

    const focusedSessionContext = focusedSession
        ? `\nCurrently Viewing Attacker Detail: IP=${focusedSession.ip}, Country=${focusedSession.countryName ?? focusedSession.country}, Client=${focusedSession.client}, HASSH=${focusedSession.fingerprint || "unknown"}, Status=${focusedSession.status}, ISP=${focusedSession.isp ?? "unknown"}, Events=${focusedSession.input?.length ?? 0}, Risk=${focusedSession.riskScore ?? 0}, SOAR=${focusedSession.soarAction ?? "none"}, MITRE=${(focusedSession.mitreTechniques ?? []).join(",") || "none"}`
        : "";

    useEffect(() => {
        const aiMsgCount = messages.filter((m) => m.role === "ai").length;
        if (aiMsgCount > lastAiMsgCountRef.current && !isOpen) {
            setHasUnread(true);
        }
        lastAiMsgCountRef.current = aiMsgCount;
    }, [messages, isOpen]);

    useEffect(() => {
        if (isOpen) {
            setHasUnread(false);
            const timer = setTimeout(() => inputRef.current?.focus(), 150);
            return () => clearTimeout(timer);
        }
    }, [isOpen]);

    const closeChat = useCallback(() => {
        setIsOpen(false);
        const active = document.activeElement;
        if (active instanceof HTMLElement && panelRef.current?.contains(active)) {
            active.blur();
        }
    }, []);

    useEffect(() => {
        if (!isOpen) return;
        const onPointerDown = (event: PointerEvent) => {
            if (panelRef.current?.contains(event.target as Node)) return;
            closeChat();
        };
        document.addEventListener("pointerdown", onPointerDown);
        return () => document.removeEventListener("pointerdown", onPointerDown);
    }, [isOpen, closeChat]);

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape" && isOpen) {
                closeChat();
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen, closeChat]);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, isLoading, isOpen]);

    const handleActionApprove = useCallback(
        async (msgIndex: number) => {
            const snapshotMsg = messagesRef.current[msgIndex];
            const actions = snapshotMsg?.actions ?? [];
            if (actions.length === 0) return;

            setMessages((prev) =>
                prev.map((m, i) => (i === msgIndex ? { ...m, actionState: "executing" as const } : m)),
            );

            for (const action of actions) {
                await executeAction(action);
            }

            const completionText = snapshotMsg?.postActionContent
                || (actions.length > 1 ? "All actions completed successfully." : "Action completed.");
            setMessages((prev) =>
                prev.map((m, i) => (i === msgIndex ? { ...m, actionState: "done" as const } : m)),
            );
            setMessages((prev) => [...prev, { role: "ai", content: completionText }]);
        },
        [executeAction],
    );

    const handleActionDeny = useCallback((msgIndex: number) => {
        setMessages((prev) =>
            prev.map((m, i) => (i === msgIndex ? { ...m, actionState: "denied" as const } : m)),
        );
        setMessages((prev) => [
            ...prev,
            { role: "ai", content: "Understood. I won't perform that action. Let me know if you need anything else." },
        ]);
    }, []);

    async function handleSend() {
        if (!input.trim() || isLoading || isExecuting) return;

        const userMsg = input.trim();
        setInput("");
        setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
        setIsLoading(true);

        const contextStr = buildAgentPromptContext({
            pathname,
            stats,
            sessions,
            activeIpCount,
            topIps,
            focusedSessionContext,
            intelligenceSnapshot,
            intelligenceFactsJson,
            messages,
            userMsg,
        });

        try {
            const res = await fetch("/api/cloudsentinel/ai-chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: userMsg, context: contextStr }),
            });
            const data = await res.json();
            const isOfflineResponse = data.response === "I am currently offline or cannot reach the LLM provider.";
            if (data.ok && data.response && !isOfflineResponse) {
                const { cleanText, postActionContent, actions: parsedActions } = parseActionsFromResponse(data.response);
                const isCasual = /^\s*(hi|hello|hey|yo|sup|what'?s?\s*up|good\s*(morning|afternoon|evening|night)|thanks|thank\s*you|ok|okay|cool|nice|great)\b/i.test(userMsg);
                const finalActions =
                    parsedActions.length > 0 ? parsedActions : (isCasual ? [] : detectIntentActions(userMsg, data.response, messages));

                const aiMessage: AgentMessage = {
                    role: "ai",
                    content: cleanText,
                    postActionContent,
                    actions: finalActions.length > 0 ? finalActions : undefined,
                    actionState: finalActions.length > 0 ? "pending" : undefined,
                };
                setMessages((prev) => [...prev, aiMessage]);
            } else if (data.error === "auth_failed") {
                setMessages((prev) => [
                    ...prev,
                    {
                        role: "ai",
                        content: "Authentication failed. The configured CLOUDSENTINEL_ADMIN_TOKEN is invalid or mismatched. Please verify your admin token configuration.",
                    },
                ]);
            } else {
                setMessages((prev) => [...prev, buildOfflineFallbackMessage(userMsg, messages)]);
            }
        } catch {
            setMessages((prev) => [...prev, buildOfflineFallbackMessage(userMsg, messages)]);
        } finally {
            setIsLoading(false);
        }
    }

    return (
        <>
            {/* Floating Launcher Button with Smooth Scale & Fade */}
            <button
                onClick={() => setIsOpen(true)}
                aria-label="Open CloudSentinel Copilot"
                className={cn(
                    "fixed bottom-[calc(5rem_+_env(safe-area-inset-bottom))] md:bottom-6 right-4 md:right-6 z-[75] w-12 h-12 md:w-13 md:h-13 rounded-full bg-transparent border border-white/40 dark:border-white/30 shadow-[0_4px_16px_rgba(0,0,0,0.25),inset_0_1px_1px_rgba(255,255,255,0.35)] flex items-center justify-center text-slate-800 dark:text-white group overflow-hidden transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                    isOpen
                        ? "opacity-0 scale-75 translate-y-2 pointer-events-none"
                        : "opacity-100 scale-100 translate-y-0 pointer-events-auto hover:scale-105 active:scale-95 hover:border-blue-400/60"
                )}
                style={{ backdropFilter: "blur(0.8px)", WebkitBackdropFilter: "blur(0.8px)" }}
            >
                {/* Clear curved glass specular shine on top half */}
                <div className="absolute inset-0 rounded-full bg-gradient-to-b from-white/20 via-transparent to-transparent pointer-events-none" />
                <Sparkles size={20} className="text-blue-500 dark:text-blue-400 drop-shadow-[0_0_8px_rgba(59,130,246,0.6)]" />
                {hasUnread && (
                    <span className="absolute top-0 right-0 w-2.5 h-2.5 bg-blue-500 rounded-full ring-2 ring-white/80 dark:ring-[#0a0a0a]/80 animate-pulse" />
                )}
            </button>

            {/* Chat Panel Window with Distinct Slide-Up from Below */}
            <div
                ref={panelRef}
                className={cn(
                    "fixed bottom-[calc(5rem_+_env(safe-area-inset-bottom))] md:bottom-6 right-4 md:right-6 z-[75] bg-slate-900/[0.06] dark:bg-black/[0.38] max-md:bg-white/95 max-md:dark:bg-[#0a0a0a]/95 border border-slate-900/15 dark:border-white/20 shadow-[0_24px_50px_rgba(15,23,42,0.16),0_4px_12px_rgba(15,23,42,0.08),inset_0_1px_1px_rgba(255,255,255,0.2)] rounded-2xl flex flex-col overflow-hidden origin-bottom transition-all duration-350 ease-[cubic-bezier(0.16,1,0.3,1)] w-[calc(100vw-32px)] md:w-96 h-[500px] max-h-[75dvh]",
                    isOpen
                        ? "opacity-100 scale-100 translate-y-0 pointer-events-auto"
                        : "opacity-0 scale-95 translate-y-14 pointer-events-none"
                )}
                style={{ backdropFilter: "blur(1.5px)", WebkitBackdropFilter: "blur(1.5px)" }}
            >
            {/* Subtle light specular shine on top rim */}
            <div className="absolute top-0 left-0 right-0 h-16 bg-gradient-to-b from-white/12 dark:from-white/8 to-transparent pointer-events-none rounded-t-2xl" />

            <div className="relative px-3.5 py-2.5 bg-slate-100/60 dark:bg-black/[0.15] border-b border-slate-200/80 dark:border-white/15 flex justify-between items-center shrink-0">
                <div className="flex items-center gap-2.5">
                    <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-blue-500/20 border border-blue-400/40 text-blue-400 shadow-[0_0_12px_rgba(59,130,246,0.3)]">
                        <Sparkles size={14} className="text-blue-400" />
                    </div>
                    <div className="flex flex-col leading-tight">
                        <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-xs tracking-tight text-slate-900 dark:text-white">CloudSentinel Copilot</span>
                            <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        </div>
                        <span className="text-[10px] text-slate-500 dark:text-slate-400">AI Security Defense</span>
                    </div>
                    {isExecuting && (
                        <span className="flex items-center gap-1 text-[10px] font-medium bg-blue-500/20 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded-full border border-blue-400/30">
                            <Loader2 size={10} className="animate-spin" />
                            Mitigating
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-0.5">
                    <button
                        type="button"
                        onClick={closeChat}
                        className="flex h-9 w-9 shrink-0 items-center justify-center hover:bg-slate-200/70 dark:hover:bg-white/10 text-slate-400 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 rounded-lg transition-colors cursor-pointer"
                        aria-label="Close copilot"
                    >
                        <X size={14} />
                    </button>
                </div>
            </div>

            <AgentMessageList
                scrollRef={scrollRef}
                messages={messages}
                isLoading={isLoading}
                isExecuting={isExecuting}
                onApprove={handleActionApprove}
                onDeny={handleActionDeny}
            />

                    <div className="relative p-2.5 bg-white/[0.06] dark:bg-black/[0.15] border-t border-white/30 dark:border-white/15 shrink-0">
                        <div className="relative flex items-center">
                            <textarea
                                ref={inputRef}
                                rows={1}
                                value={input}
                                onChange={(e) => {
                                    setInput(e.target.value);
                                    e.target.style.height = "auto";
                                    e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
                                }}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && !e.shiftKey) {
                                        e.preventDefault();
                                        handleSend();
                                        e.currentTarget.style.height = "auto";
                                    }
                                }}
                                placeholder={isExecuting ? "Agent is working..." : "Ask or command the agent..."}
                                disabled={isExecuting}
                                className="w-full bg-white/40 dark:bg-black/30 border border-white/40 dark:border-white/20 rounded-xl pl-3.5 pr-12 py-2.5 text-xs outline-none focus:ring-1 focus:ring-blue-500/60 focus:border-blue-500/60 text-slate-900 dark:text-white placeholder:text-slate-500 dark:placeholder:text-slate-400 disabled:opacity-50 resize-none overflow-hidden block transition-all shadow-[inset_0_1px_2px_rgba(0,0,0,0.1)] text-left backdrop-blur-sm"
                                style={{ minHeight: "36px" }}
                            />
                            <button
                                onClick={handleSend}
                                disabled={!input.trim() || isLoading || isExecuting}
                                className="absolute right-1.5 h-9 w-9 flex items-center justify-center rounded-lg text-white transition-all active:scale-95 bg-blue-600 hover:bg-blue-500 shadow-[0_0_10px_rgba(37,99,235,0.4)] disabled:opacity-30 disabled:bg-slate-400 dark:disabled:bg-slate-700"
                            >
                                <Send size={12} />
                            </button>
                        </div>
                    </div>
        </div>
        </>
    );
}
