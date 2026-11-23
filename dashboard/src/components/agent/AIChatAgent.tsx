"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { Sparkles, Send, X, Loader2, Minimize2, Maximize2 } from "lucide-react";
import { usePathname } from "next/navigation";
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
    const [isMinimized, setIsMinimized] = useState(false);
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
        const updateFocusIp = () => {
            const params = new URLSearchParams(window.location.search);
            setFocusIp(params.get("focusIp")?.trim() ?? "");
        };
        const patchHistoryForLocationChange = () => {
            const historyAny = window.history as History & { __cloudsentinelPatched?: boolean };
            if (historyAny.__cloudsentinelPatched) return;
            const wrap = (method: "pushState" | "replaceState") => {
                const original = window.history[method];
                window.history[method] = function (...args: Parameters<History[typeof method]>) {
                    const result = original.apply(this, args);
                    window.dispatchEvent(new Event("locationchange"));
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
        if (aiMsgCount > lastAiMsgCountRef.current && (!isOpen || isMinimized)) {
            setHasUnread(true);
        }
        lastAiMsgCountRef.current = aiMsgCount;
    }, [messages, isOpen, isMinimized]);

    useEffect(() => {
        if (isOpen && !isMinimized) {
            setHasUnread(false);
        }
    }, [isOpen, isMinimized]);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, isLoading, isOpen, isMinimized]);

    const handleActionApprove = useCallback(
        async (msgIndex: number) => {
            const snapshotMsg = messagesRef.current[msgIndex];
            if (!snapshotMsg?.actions || snapshotMsg.actions.length === 0) return;
            let actions: NonNullable<AgentMessage["actions"]> = [];
            let postActionContent = "";
            setMessages((prev) => {
                const msg = prev[msgIndex];
                actions = msg?.actions ?? [];
                postActionContent = msg?.postActionContent ?? "";
                if (!msg || actions.length === 0) {
                    return prev;
                }
                return prev.map((m, i) => (i === msgIndex ? { ...m, actionState: "executing" as const } : m));
            });
            if (!actions || actions.length === 0) return;

            for (const action of actions) {
                await executeAction(action);
            }

            let completionText = postActionContent || (actions.length > 1 ? "All actions completed successfully." : "Action completed.");
            setMessages((prev) => {
                const updated = prev.map((m, i) => (i === msgIndex ? { ...m, actionState: "done" as const } : m));
                const latestMsg = updated[msgIndex];
                if (latestMsg?.postActionContent) {
                    completionText = latestMsg.postActionContent;
                }
                return updated;
            });

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

    const gradientStyle = {
        background: "linear-gradient(135deg, #1d4ed8, #2563eb, #3b82f6, #4f46e5, #0284c7, #1d4ed8)",
        backgroundSize: "300% 300%",
        animation: "ai-gradient-pan 12s ease infinite",
    };

    if (!isOpen) {
        return (
            <>
                <style>{`
                    @keyframes ai-gradient-pan {
                        0% { background-position: 0% 50%; }
                        50% { background-position: 100% 50%; }
                        100% { background-position: 0% 50%; }
                    }
                `}</style>
                <button
                    onClick={() => setIsOpen(true)}
                    style={gradientStyle}
                    aria-label="Open CloudSentinel Copilot"
                    className="fixed bottom-20 md:bottom-6 right-4 md:right-6 z-[100] w-13 h-13 md:w-14 md:h-14 hover:opacity-95 rounded-full shadow-xl shadow-blue-600/35 flex items-center justify-center text-white transition-all hover:scale-105 active:scale-95 border-2 border-white/25 backdrop-blur-sm"
                >
                    <Sparkles size={22} className="drop-shadow-sm" />
                    {hasUnread && (
                        <span className="absolute top-0.5 right-0.5 w-3 h-3 bg-sky-400 border-2 border-slate-900 rounded-full animate-pulse" />
                    )}
                </button>
            </>
        );
    }

    return (
        <div
            className={`fixed bottom-20 md:bottom-6 right-4 md:right-6 z-[100] bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/10 shadow-2xl rounded-2xl flex flex-col overflow-hidden transition-all duration-300 ${isMinimized ? "w-[calc(100vw-32px)] md:w-72 h-14" : "w-[calc(100vw-32px)] md:w-96 h-[500px] max-h-[75vh]"}`}
        >
            <style>{`
                @keyframes ai-gradient-pan {
                    0% { background-position: 0% 50%; }
                    50% { background-position: 100% 50%; }
                    100% { background-position: 0% 50%; }
                }
            `}</style>

            <div
                style={gradientStyle}
                className="text-white px-3.5 py-3 flex justify-between items-center shrink-0 cursor-pointer shadow-md"
                onClick={() => setIsMinimized(!isMinimized)}
            >
                <div className="flex items-center gap-2.5">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/15 backdrop-blur-sm">
                        <Sparkles size={16} />
                    </div>
                    <div className="flex flex-col leading-tight">
                        <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-xs tracking-tight">CloudSentinel Copilot</span>
                            <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        </div>
                        <span className="text-[10.5px] text-blue-100/80">AI Security Defense</span>
                    </div>
                    {isExecuting && (
                        <span className="flex items-center gap-1 text-[10px] bg-white/20 px-2 py-0.5 rounded-full backdrop-blur-sm">
                            <Loader2 size={10} className="animate-spin" />
                            Mitigating
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            setIsMinimized(!isMinimized);
                        }}
                        className="p-1 hover:bg-white/20 rounded-md transition-colors"
                        aria-label={isMinimized ? "Maximize copilot" : "Minimize copilot"}
                    >
                        {isMinimized ? <Maximize2 size={13} /> : <Minimize2 size={13} />}
                    </button>
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            setIsOpen(false);
                        }}
                        className="p-1 hover:bg-white/20 rounded-md transition-colors"
                        aria-label="Close copilot"
                    >
                        <X size={13} />
                    </button>
                </div>
            </div>

            {!isMinimized && (
                <>
                    <AgentMessageList
                        scrollRef={scrollRef}
                        messages={messages}
                        isLoading={isLoading}
                        isExecuting={isExecuting}
                        onApprove={handleActionApprove}
                        onDeny={handleActionDeny}
                    />

                    <div className="p-3 bg-white dark:bg-[#0a0a0a] border-t border-slate-200 dark:border-white/5 shrink-0">
                        <div className="relative flex items-center">
                            <textarea
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
                                className="w-full bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-2xl pl-4 pr-10 py-2 text-[13px] outline-none focus:ring-1 focus:ring-blue-600 text-slate-900 dark:text-white placeholder:text-slate-500 disabled:opacity-50 resize-none overflow-hidden block"
                                style={{ minHeight: "36px" }}
                            />
                            <button
                                onClick={handleSend}
                                disabled={!input.trim() || isLoading || isExecuting}
                                className={`absolute right-1 w-8 h-8 flex items-center justify-center rounded-full text-white transition-colors ${!input.trim() || isLoading || isExecuting ? "bg-slate-400 dark:bg-slate-600" : "bg-blue-600 hover:bg-blue-700"}`}
                            >
                                <Send size={12} />
                            </button>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
