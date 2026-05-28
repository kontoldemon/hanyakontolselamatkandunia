"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Bot, Send, X, Loader2, Minimize2, Maximize2, ShieldCheck, ShieldX, Zap } from "lucide-react";
import { usePathname } from "next/navigation";
import { useCapturedSessions, useDashboardStats } from "@/lib/liveEvents";
import { useAgent } from "@/lib/AgentContext";
import type { AgentMessage } from "@/lib/agentActions";
import { parseActionsFromResponse, detectIntentActions } from "@/lib/agentActions";

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
    const pathname = usePathname();
    const { executeAction, isExecuting } = useAgent();
    const lastAiMsgCountRef = useRef(1);

    // Grab some context to send to the backend
    const stats = useDashboardStats();
    const sessions = useCapturedSessions();
    const activeIpCount = sessions.filter((s) => s.status === "Active").length;

    // Build a brief list of top IPs for the AI to reference
    const topIps = sessions.slice(0, 8).map((s) => `${s.ip} (${s.country}, ${s.status})`).join(", ");

    // Detect focused session IP from URL (avoids useSearchParams Suspense requirement)
    const [focusIp, setFocusIp] = useState("");
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        setFocusIp(params.get("focusIp")?.trim() ?? "");
    }, [pathname]);
    const focusedSession = focusIp ? sessions.find((s) => s.ip === focusIp) : null;

    // Build contextual info about the focused session
    const focusedSessionContext = focusedSession
        ? `\nCurrently Viewing Attacker Detail: IP=${focusedSession.ip}, Country=${focusedSession.countryName ?? focusedSession.country}, Client=${focusedSession.client}, HASSH=${focusedSession.fingerprint || "unknown"}, Status=${focusedSession.status}, ISP=${focusedSession.isp ?? "unknown"}, Events=${focusedSession.input?.length ?? 0}, Risk=${focusedSession.riskScore ?? 0}, SOAR=${focusedSession.soarAction ?? "none"}, MITRE=${(focusedSession.mitreTechniques ?? []).join(",") || "none"}`
        : "";

    // Track unread AI responses
    useEffect(() => {
        const aiMsgCount = messages.filter((m) => m.role === "ai").length;
        if (aiMsgCount > lastAiMsgCountRef.current) {
            // New AI message arrived
            if (!isOpen || isMinimized) {
                setHasUnread(true);
            }
        }
        lastAiMsgCountRef.current = aiMsgCount;
    }, [messages, isOpen, isMinimized]);

    // Clear unread when chat is opened/unminimized
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



    // ─── Action Execution ────────────────────────────────────────────────

    const handleActionApprove = useCallback(
        async (msgIndex: number, actionIndex: number) => {
            const msg = messages[msgIndex];
            if (!msg?.actions?.[actionIndex]) return;

            const action = msg.actions[actionIndex];

            // Mark as executing
            setMessages((prev) =>
                prev.map((m, i) => (i === msgIndex ? { ...m, actionState: "executing" as const } : m)),
            );

            const result = await executeAction(action);

            // Mark as done
            setMessages((prev) =>
                prev.map((m, i) => (i === msgIndex ? { ...m, actionState: "done" as const } : m)),
            );

            // Append agent completion message
            setMessages((prev) => [
                ...prev,
                {
                    role: "ai",
                    content: result,
                },
            ]);
        },
        [messages, executeAction],
    );

    const handleActionDeny = useCallback(
        (msgIndex: number) => {
            setMessages((prev) =>
                prev.map((m, i) => (i === msgIndex ? { ...m, actionState: "denied" as const } : m)),
            );
            setMessages((prev) => [
                ...prev,
                { role: "ai", content: "Understood. I won't perform that action. Let me know if you need anything else." },
            ]);
        },
        [],
    );

    // ─── Send Message ────────────────────────────────────────────────────

    async function handleSend() {
        if (!input.trim() || isLoading || isExecuting) return;

        const userMsg = input.trim();
        setInput("");
        setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
        setIsLoading(true);

        const recentHistory = messages.slice(-5).map(m => `${m.role === "user" ? "User" : "AI"}: ${m.content}`).join("\n");

        // Build context string with system instructions for action markers
        const contextStr = `
Current Page: ${pathname}
Total Active Connections: ${stats.activeSessions}
Total Captured IPs: ${sessions.length} (Live: ${activeIpCount})
Total Attacks: ${stats.totalAttacks}
MTTB: ${stats.mttb}
Top IPs: ${topIps}${focusedSessionContext}
${recentHistory ? `\nRECENT CONVERSATION HISTORY:\n${recentHistory}\n` : ""}

SYSTEM INSTRUCTIONS:
You are CloudSentinel AI, an autonomous cybersecurity agent that FULLY CONTROLS the dashboard.
You can navigate pages, click buttons, change dropdowns, set filters, search, and block IPs.

PERSONALITY RULES:
1. For casual greetings (hi, hello, hey, what's up, etc), respond warmly and briefly. Ask how you can help with the honeypot monitoring. Do NOT suggest any actions or include any ACTION markers for greetings.
2. For questions about specific IPs, attackers, or threats, always reference the focused session context above if available.
3. Be conversational and human. Avoid robotic or overly technical responses unless the user asks for technical detail.
4. Never generate ACTION markers unless the user is clearly requesting an action (navigate, block, export, change settings, etc).

RESPONSE RULES:
1. Provide a concise technical explanation first (2-3 sentences max).
2. Append action markers ONLY for actionable requests. You may include MULTIPLE markers.
3. Before each marker, write a brief sentence like "I can do that for you" or "Let me change that".
4. Do NOT explain markers. Use them naturally. Be direct. No filler.

NAVIGATION MARKERS:
[ACTION:navigate_session:IP] — View attacker session details
[ACTION:navigate_page:PATH] — Go to page (/ = War Room, /sessions, /intelligence, /settings)
[ACTION:show_threat_map:] — Focus the global threat map
[ACTION:block_ip:IP] — Block an IP at the sensor firewall
[ACTION:export_data:] — Export sensor JSON data
[ACTION:toggle_exposure:] — Toggle honeypot exposure on/off

UI CONTROL MARKERS (for controlling dropdowns, search, filters, toggles):
[ACTION:ui_command:sessions.search=VALUE] — Set sessions search query
[ACTION:ui_command:sessions.filter=VALUE] — Filter sessions (all or active)
[ACTION:ui_command:settings.deception_level=VALUE] — Set deception level (High (Full VFS), Medium (Restricted), Low (Port listener))
[ACTION:ui_command:settings.hassh_action=VALUE] — Set HASSH action (Immediate Drop, Allow & Monitor, Tarpit)
[ACTION:ui_command:settings.hassh_threshold=VALUE] — Set HASSH confidence threshold (0-100)
[ACTION:ui_command:settings.soar_trigger=VALUE] — Set SOAR trigger (MITRE Match (>1), Auth Spike (>10/m), Any Input)
[ACTION:ui_command:settings.soar_execution=VALUE] — Set SOAR execution path (Lambda (Warm), Lambda (Cold), Local Docker)
[ACTION:ui_command:settings.fake_keys=VALUE] — Toggle fake AWS keys (true/false)
[ACTION:ui_command:intel.sort=VALUE] — Sort commands (most or least)
[ACTION:ui_command:intel.search=VALUE] — Search attacker commands
[ACTION:ui_command:replay.fullscreen=toggle] — Toggle terminal replay fullscreen
[ACTION:ui_command:replay.mode=VALUE] — Set replay filter (attacker or both)
[ACTION:ui_command:replay.copy=trigger] — Copy terminal replay to clipboard
[ACTION:ui_command:socket.fullscreen=toggle] — Toggle socket telemetry fullscreen

GLOBAL CONTROLS (work from any page):
[ACTION:ui_command:sidebar.toggle=VALUE] — Collapse or expand sidebar (collapse, expand, or toggle)
[ACTION:ui_command:sidebar.theme=VALUE] — Switch theme (dark, light, or toggle)
        `.trim();

        try {
            const res = await fetch("/api/cloudsentinel/ai-chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: userMsg, context: contextStr }),
            });
            const data = await res.json();
            const isOfflineResponse = data.response === "I am currently offline or cannot reach the LLM provider.";
            if (data.ok && data.response && !isOfflineResponse) {
                // Parse AI response for action markers
                const { cleanText, actions: parsedActions } = parseActionsFromResponse(data.response);

                // If no markers found, try fallback intent detection
                // But skip fallback for casual/greeting messages
                const isCasual = /^\s*(hi|hello|hey|yo|sup|what'?s?\s*up|good\s*(morning|afternoon|evening|night)|thanks|thank\s*you|ok|okay|cool|nice|great)\b/i.test(userMsg);
                const finalActions =
                    parsedActions.length > 0 ? parsedActions : (isCasual ? [] : detectIntentActions(userMsg, data.response, messages));

                const aiMessage: AgentMessage = {
                    role: "ai",
                    content: cleanText,
                    actions: finalActions.length > 0 ? finalActions : undefined,
                    actionState: finalActions.length > 0 ? "pending" : undefined,
                };
                setMessages((prev) => [...prev, aiMessage]);
            } else {
                if (data.error === "auth_failed") {
                    setMessages((prev) => [
                        ...prev,
                        {
                            role: "ai",
                            content: "Authentication failed. The configured CLOUDSENTINEL_ADMIN_TOKEN is invalid or mismatched. Please verify your admin token configuration."
                        }
                    ]);
                } else {
                    const offlineActions = detectIntentActions(userMsg, "", messages);
                    const isCasual = /^\s*(hi|hello|hey|yo|sup|what'?s?\s*up|good\s*(morning|afternoon|evening|night))\b/i.test(userMsg);
                    const isThanks = /^\s*(thanks|thank\s*you|ty)\b/i.test(userMsg);

                    if (offlineActions.length > 0) {
                        setMessages((prev) => [
                            ...prev,
                            {
                                role: "ai",
                                content: "I couldn't reach the backend LLM service, but I've detected your command locally! What action would you like to take?",
                                actions: offlineActions,
                                actionState: "pending"
                            }
                        ]);
                    } else if (isCasual) {
                        setMessages((prev) => [
                            ...prev,
                            {
                                role: "ai",
                                content: "Hi there! I'm operating in offline mode right now, but I'm ready to assist. You can ask me to do things like 'go to sessions' or 'switch to dark mode'!"
                            }
                        ]);
                    } else if (isThanks) {
                        setMessages((prev) => [
                            ...prev,
                            {
                                role: "ai",
                                content: "You're very welcome! Let me know if you want me to navigate or perform any other dashboard actions."
                            }
                        ]);
                    } else {
                        setMessages((prev) => [
                            ...prev,
                            {
                                role: "ai",
                                content: "I couldn't reach the backend LLM service. (Offline Mode: you can still type commands like 'go to sessions' or 'block [IP]')"
                            }
                        ]);
                    }
                }
            }
        } catch {
            const offlineActions = detectIntentActions(userMsg, "", messages);
            const isCasual = /^\s*(hi|hello|hey|yo|sup|what'?s?\s*up|good\s*(morning|afternoon|evening|night))\b/i.test(userMsg);
            const isThanks = /^\s*(thanks|thank\s*you|ty)\b/i.test(userMsg);

            if (offlineActions.length > 0) {
                setMessages((prev) => [
                    ...prev,
                    {
                        role: "ai",
                        content: "I couldn't reach the backend LLM service, but I've detected your command locally! What action would you like to take?",
                        actions: offlineActions,
                        actionState: "pending"
                    }
                ]);
            } else if (isCasual) {
                setMessages((prev) => [
                    ...prev,
                    {
                        role: "ai",
                        content: "Hi there! I'm operating in offline mode right now, but I'm ready to assist. You can ask me to do things like 'go to sessions' or 'switch to dark mode'!"
                    }
                ]);
            } else if (isThanks) {
                setMessages((prev) => [
                    ...prev,
                    {
                        role: "ai",
                        content: "You're very welcome! Let me know if you want me to navigate or perform any other dashboard actions."
                    }
                ]);
            } else {
                setMessages((prev) => [
                    ...prev,
                    {
                        role: "ai",
                        content: "I couldn't reach the backend LLM service. (Offline Mode: you can still type commands like 'go to sessions' or 'block [IP]')"
                    }
                ]);
            }
        } finally {
            setIsLoading(false);
        }
    }

    const gradientStyle = {
        background: "linear-gradient(135deg, #3b82f6, #8b5cf6, #ec4899, #f59e0b, #3b82f6)",
        backgroundSize: "300% 300%",
        animation: "ai-gradient-pan 12s ease infinite",
    };

    function formatAiText(text: string) {
        const clean = text.replace(/—/g, "-");
        const parts = clean.split(/(\*\*.*?\*\*)/g);
        return parts.map((part, i) => {
            if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={i} className="font-bold">{part.slice(2, -2)}</strong>;
            }
            return part;
        });
    }

    // ─── Closed State (FAB button) ───────────────────────────────────────

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
                    className="fixed bottom-20 md:bottom-6 right-4 md:right-6 z-[100] w-14 h-14 hover:opacity-90 rounded-full shadow-2xl flex items-center justify-center text-white transition-transform hover:scale-105 border-2 border-white/20"
                >
                    <Bot size={24} />
                    {hasUnread && (
                        <span className="absolute top-0 right-0 w-3 h-3 bg-red-500 border-2 border-[#0a0a0a] rounded-full animate-pulse"></span>
                    )}
                </button>
            </>
        );
    }

    // ─── Open State ──────────────────────────────────────────────────────

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

            {/* Header */}
            <div
                style={gradientStyle}
                className="text-white p-3 flex justify-between items-center shrink-0 cursor-pointer"
                onClick={() => setIsMinimized(!isMinimized)}
            >
                <div className="flex items-center gap-2">
                    <Bot size={18} />
                    <span className="font-semibold text-sm">CloudSentinel AI</span>
                    {isExecuting && (
                        <span className="flex items-center gap-1 text-[10px] bg-white/20 px-2 py-0.5 rounded-full">
                            <Loader2 size={10} className="animate-spin" />
                            Working
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            setIsMinimized(!isMinimized);
                        }}
                        className="p-1 hover:bg-white/20 rounded"
                    >
                        {isMinimized ? <Maximize2 size={14} /> : <Minimize2 size={14} />}
                    </button>
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            setIsOpen(false);
                        }}
                        className="p-1 hover:bg-white/20 rounded"
                    >
                        <X size={14} />
                    </button>
                </div>
            </div>

            {/* Chat Area */}
            {!isMinimized && (
                <>
                    <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50 dark:bg-[#050505]">
                        {messages.map((msg, i) => (
                            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                                <div className="max-w-[90%] flex flex-col gap-2">
                                    {/* Message Bubble */}
                                    <div
                                        className={`rounded-2xl px-3 py-2 text-[13px] leading-relaxed shadow-sm ${
                                            msg.role === "user"
                                                ? "bg-blue-600 text-white rounded-br-none"
                                                : "bg-white dark:bg-[#151515] border border-slate-200 dark:border-white/5 text-slate-800 dark:text-slate-200 rounded-bl-none"
                                        }`}
                                    >
                                        {formatAiText(msg.content)}
                                    </div>

                                    {/* Action Cards */}
                                    {msg.actions && msg.actions.length > 0 && (
                                        <div className="space-y-2">
                                            {msg.actions.map((action, ai) => (
                                                <div
                                                    key={ai}
                                                    className="bg-white dark:bg-[#111] border border-slate-200 dark:border-white/10 rounded-xl p-3 shadow-sm"
                                                >
                                                    <div className="flex items-start gap-2 mb-2">
                                                        <Zap size={14} className="text-amber-500 shrink-0 mt-0.5" />
                                                        <div>
                                                            <p className="text-[12px] font-semibold text-slate-800 dark:text-slate-200">
                                                                {action.label}
                                                            </p>
                                                            <p className="text-[10px] text-slate-500 dark:text-slate-400">
                                                                {action.description}
                                                            </p>
                                                        </div>
                                                    </div>

                                                    {/* Action State Rendering */}
                                                    {msg.actionState === "pending" && (
                                                        <div className="flex items-center gap-2 mt-1">
                                                            <button
                                                                onClick={() => handleActionApprove(i, ai)}
                                                                disabled={isExecuting}
                                                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-[11px] font-semibold hover:bg-blue-700 transition-all disabled:opacity-50 shadow-sm"
                                                            >
                                                                <ShieldCheck size={12} />
                                                                Allow
                                                            </button>
                                                            <button
                                                                onClick={() => handleActionDeny(i)}
                                                                disabled={isExecuting}
                                                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-400 text-[11px] font-semibold hover:bg-slate-200 dark:hover:bg-white/10 transition-colors disabled:opacity-50 border border-slate-200 dark:border-white/10"
                                                            >
                                                                <ShieldX size={12} />
                                                                Deny
                                                            </button>
                                                        </div>
                                                    )}

                                                    {msg.actionState === "executing" && (
                                                        <div className="flex items-center gap-2 mt-1 text-[11px] text-blue-600 dark:text-blue-400 font-medium">
                                                            <Loader2 size={12} className="animate-spin" />
                                                            Executing action...
                                                        </div>
                                                    )}

                                                    {msg.actionState === "done" && (
                                                        <div className="flex items-center gap-2 mt-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                                                            <ShieldCheck size={12} />
                                                            Action completed
                                                        </div>
                                                    )}

                                                    {msg.actionState === "denied" && (
                                                        <div className="flex items-center gap-2 mt-1 text-[11px] text-slate-400 font-medium">
                                                            <ShieldX size={12} />
                                                            Action declined
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                        {isLoading && (
                            <div className="flex justify-start">
                                <div className="bg-white dark:bg-[#151515] border border-slate-200 dark:border-white/5 text-slate-800 dark:text-slate-200 rounded-2xl rounded-bl-none px-4 py-3 shadow-sm">
                                    <Loader2 size={14} className="animate-spin text-purple-500" />
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Input Area */}
                    <div className="p-3 bg-white dark:bg-[#0a0a0a] border-t border-slate-200 dark:border-white/5 shrink-0">
                        <div className="relative flex items-center">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter") {
                                        e.preventDefault();
                                        handleSend();
                                    }
                                }}
                                placeholder={isExecuting ? "Agent is working..." : "Ask or command the agent..."}
                                disabled={isExecuting}
                                className="w-full bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-full pl-4 pr-10 py-2 text-[13px] outline-none focus:ring-1 focus:ring-blue-600 text-slate-900 dark:text-white placeholder:text-slate-500 disabled:opacity-50"
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