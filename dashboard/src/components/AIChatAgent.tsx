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

    // Grab some context to send to the backend
    const stats = useDashboardStats();
    const sessions = useCapturedSessions();
    const activeIpCount = sessions.filter((s) => s.status === "Active").length;

    // Build a brief list of top IPs for the AI to reference
    const topIps = sessions.slice(0, 8).map((s) => `${s.ip} (${s.country}, ${s.status})`).join(", ");

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
                    content: `✓ Done — ${result}`,
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

        // Build context string with system instructions for action markers
        const contextStr = `
Current Page: ${pathname}
Total Active Connections: ${stats.activeSessions}
Total Captured IPs: ${sessions.length} (Live: ${activeIpCount})
Total Attacks: ${stats.totalAttacks}
MTTB: ${stats.mttb}
Top IPs: ${topIps}

SYSTEM INSTRUCTIONS:
You are CloudSentinel AI, an autonomous cybersecurity agent that FULLY CONTROLS the dashboard.
You can navigate pages, click buttons, change dropdowns, set filters, search, and block IPs.

RESPONSE RULES:
1. Provide a concise technical explanation first (2-3 sentences max).
2. Append action markers for ANY actionable request. You may include MULTIPLE markers.
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
            if (data.ok && data.response) {
                // Parse AI response for action markers
                const { cleanText, actions: parsedActions } = parseActionsFromResponse(data.response);

                // If no markers found, try fallback intent detection
                const finalActions =
                    parsedActions.length > 0 ? parsedActions : detectIntentActions(userMsg, data.response);

                const aiMessage: AgentMessage = {
                    role: "ai",
                    content: cleanText,
                    actions: finalActions.length > 0 ? finalActions : undefined,
                    actionState: finalActions.length > 0 ? "pending" : undefined,
                };
                setMessages((prev) => [...prev, aiMessage]);
            } else {
                setMessages((prev) => [
                    ...prev,
                    { role: "ai", content: "Sorry, I couldn't reach the backend LLM service. The sensor API may be offline." },
                ]);
            }
        } catch {
            setMessages((prev) => [...prev, { role: "ai", content: "Network error occurred." }]);
        } finally {
            setIsLoading(false);
        }
    }

    // ─── Gradient Style ──────────────────────────────────────────────────

    const gradientStyle = {
        background: "linear-gradient(110deg, #4285f4 0%, #9b72cb 25%, #d96570 50%, #fbbc05 75%, #4285f4 100%)",
        backgroundSize: "200% 200%",
        animation: "ai-gradient-anim 6s ease-in-out infinite",
    };

    // ─── Closed State (FAB button) ───────────────────────────────────────

    if (!isOpen) {
        return (
            <>
                <style>{`
                    @keyframes ai-gradient-anim {
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
                    <span className="absolute top-0 right-0 w-3 h-3 bg-red-500 border-2 border-[#0a0a0a] rounded-full animate-pulse"></span>
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
                @keyframes ai-gradient-anim {
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
                                        {msg.content}
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
                                                                style={gradientStyle}
                                                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-white text-[11px] font-semibold hover:opacity-90 transition-all disabled:opacity-50 shadow-sm"
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
                                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                                placeholder={isExecuting ? "Agent is working..." : "Ask or command the agent..."}
                                disabled={isExecuting}
                                className="w-full bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-full pl-4 pr-10 py-2 text-[13px] outline-none focus:ring-1 focus:ring-purple-500 text-slate-900 dark:text-white placeholder:text-slate-500 disabled:opacity-50"
                            />
                            <button
                                onClick={handleSend}
                                disabled={!input.trim() || isLoading || isExecuting}
                                style={input.trim() && !isLoading && !isExecuting ? gradientStyle : {}}
                                className={`absolute right-1 w-8 h-8 flex items-center justify-center rounded-full text-white transition-colors ${!input.trim() || isLoading || isExecuting ? "bg-slate-400 dark:bg-slate-600" : "hover:opacity-90"}`}
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