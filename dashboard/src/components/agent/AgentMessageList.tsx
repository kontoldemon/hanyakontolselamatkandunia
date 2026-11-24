"use client";

import type { RefObject } from "react";
import { Loader2, ShieldCheck, ShieldX, Zap } from "lucide-react";
import { detectIntentActions, type AgentMessage } from "@/lib/agentActions";

export function buildOfflineFallbackMessage(userMsg: string, history: AgentMessage[]): AgentMessage {
    const offlineActions = detectIntentActions(userMsg, "", history);
    const isCasual = /^\s*(hi|hello|hey|yo|sup|what'?s?\s*up|good\s*(morning|afternoon|evening|night))\b/i.test(userMsg);
    const isThanks = /^\s*(thanks|thank\s*you|ty)\b/i.test(userMsg);

    if (offlineActions.length > 0) {
        return {
            role: "ai",
            content: "I couldn't reach the backend LLM service, but I've detected your command locally! What action would you like to take?",
            actions: offlineActions,
            actionState: "pending",
        };
    }
    if (isCasual) {
        return {
            role: "ai",
            content: "Hi there! I'm operating in offline mode right now, but I'm ready to assist. You can ask me to do things like 'go to sessions' or 'switch to dark mode'!",
        };
    }
    if (isThanks) {
        return {
            role: "ai",
            content: "You're very welcome! Let me know if you want me to navigate or perform any other dashboard actions.",
        };
    }
    return {
        role: "ai",
        content: "I couldn't reach the backend LLM service. (Offline Mode: you can still type commands like 'go to sessions' or 'block [IP]')",
    };
}

function formatAiText(text: string) {
    const clean = text.replace(/—/g, "-");
    const parts = clean.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
            return <strong key={i} className="font-bold">{part.slice(2, -2)}</strong>;
        }
        return part;
    });
}

interface AgentMessageListProps {
    scrollRef: RefObject<HTMLDivElement | null>;
    messages: AgentMessage[];
    isLoading: boolean;
    isExecuting: boolean;
    onApprove: (msgIndex: number) => void;
    onDeny: (msgIndex: number) => void;
}

export default function AgentMessageList({
    scrollRef,
    messages,
    isLoading,
    isExecuting,
    onApprove,
    onDeny,
}: AgentMessageListProps) {
    return (
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-3.5 space-y-3 bg-transparent terminal-scrollbar">
            {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div className="max-w-[90%] flex flex-col gap-2">
                        <div
                            className={`whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed text-left ${
                                msg.role === "user"
                                    ? "bg-blue-600/60 dark:bg-blue-600/50 text-white rounded-br-xs border border-blue-400/40 shadow-[0_4px_16px_rgba(37,99,235,0.25),inset_0_1px_1px_rgba(255,255,255,0.3)]"
                                    : "bg-white/10 dark:bg-white/[0.04] border border-white/20 dark:border-white/10 text-slate-800 dark:text-slate-100 rounded-bl-xs shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)]"
                            }`}
                        >
                            {formatAiText(msg.content)}
                        </div>

                        {msg.actions && msg.actions.length > 0 && (
                            <div className="space-y-2 mt-1">
                                {msg.actions.map((action, ai) => (
                                    <div
                                        key={ai}
                                        className="bg-white/10 dark:bg-white/[0.03] border border-white/20 dark:border-white/10 rounded-xl p-3 shadow-xs flex items-start gap-2.5 text-left"
                                    >
                                        <Zap size={14} className="text-amber-500 shrink-0 mt-0.5" />
                                        <div>
                                            <p className="text-[11.5px] font-semibold text-slate-800 dark:text-slate-200">
                                                {action.label}
                                            </p>
                                            <p className="text-[10px] text-slate-500 dark:text-slate-400">
                                                {action.description}
                                            </p>
                                        </div>
                                    </div>
                                ))}

                                {msg.actionState === "pending" && (
                                    <div className="flex items-center gap-2 mt-2 pl-1">
                                        <button
                                            onClick={() => onApprove(i)}
                                            disabled={isExecuting}
                                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-[11px] font-semibold hover:bg-blue-500 transition-all disabled:opacity-50 shadow-[0_0_10px_rgba(37,99,235,0.3)]"
                                        >
                                            <ShieldCheck size={12} />
                                            {msg.actions.length > 1 ? "Allow All" : "Allow"}
                                        </button>
                                        <button
                                            onClick={() => onDeny(i)}
                                            disabled={isExecuting}
                                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-400 text-[11px] font-semibold hover:bg-slate-200 dark:hover:bg-white/10 transition-colors disabled:opacity-50 border border-slate-200 dark:border-white/10"
                                        >
                                            <ShieldX size={12} />
                                            {msg.actions.length > 1 ? "Deny All" : "Deny"}
                                        </button>
                                    </div>
                                )}

                                {msg.actionState === "executing" && (
                                    <div className="flex items-center gap-2 mt-2 pl-1 text-[11px] text-blue-600 dark:text-blue-400 font-medium">
                                        <Loader2 size={12} className="animate-spin" />
                                        Executing {msg.actions.length > 1 ? "actions" : "action"}...
                                    </div>
                                )}

                                {msg.actionState === "done" && (
                                    <div className="flex items-center gap-2 mt-2 pl-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                                        <ShieldCheck size={12} />
                                        {msg.actions.length > 1 ? "Actions completed" : "Action completed"}
                                    </div>
                                )}

                                {msg.actionState === "denied" && (
                                    <div className="flex items-center gap-2 mt-2 pl-1 text-[11px] text-slate-400 font-medium">
                                        <ShieldX size={12} />
                                        {msg.actions.length > 1 ? "Actions declined" : "Action declined"}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            ))}
            {isLoading && (
                <div className="flex justify-start">
                    <div className="bg-white/40 dark:bg-white/[0.04] border border-white/40 dark:border-white/10 text-slate-800 dark:text-slate-200 rounded-2xl rounded-bl-xs px-3.5 py-2.5 shadow-xs backdrop-blur-xl">
                        <Loader2 size={13} className="animate-spin text-blue-500" />
                    </div>
                </div>
            )}
        </div>
    );
}
