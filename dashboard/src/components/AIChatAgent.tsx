"use client";

import { useState, useRef, useEffect } from "react";
import { Bot, Send, X, Loader2, Minimize2, Maximize2 } from "lucide-react";
import { usePathname } from "next/navigation";
import { useCapturedSessions, useDashboardStats } from "@/lib/liveEvents";

export default function AIChatAgent() {
    const [isOpen, setIsOpen] = useState(false);
    const [isMinimized, setIsMinimized] = useState(false);
    const [messages, setMessages] = useState<{ role: "user" | "ai", content: string }[]>([
        { role: "ai", content: "Hi! I'm CloudSentinel AI. I can explain what's happening on the dashboard right now. What would you like to know?" }
    ]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);
    const pathname = usePathname();
    
    // Grab some context to send to the backend
    const stats = useDashboardStats();
    const sessions = useCapturedSessions();
    const activeIpCount = sessions.filter(s => s.status === "Active").length;

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, isLoading, isOpen, isMinimized]);

    async function handleSend() {
        if (!input.trim() || isLoading) return;

        const userMsg = input.trim();
        setInput("");
        setMessages(prev => [...prev, { role: "user", content: userMsg }]);
        setIsLoading(true);

        // Build context
        const contextStr = `
Current Page: ${pathname}
Total Active Connections: ${stats.activeSessions}
Total Captured IPs: ${sessions.length} (Live: ${activeIpCount})
Total Attacks: ${stats.totalAttacks}
MTTB: ${stats.mttb}
        `.trim();

        try {
            const res = await fetch("/api/cloudsentinel/ai-chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: userMsg, context: contextStr })
            });
            const data = await res.json();
            if (data.ok && data.response) {
                setMessages(prev => [...prev, { role: "ai", content: data.response }]);
            } else {
                setMessages(prev => [...prev, { role: "ai", content: "Sorry, I couldn't reach the backend LLM service." }]);
            }
        } catch {
            setMessages(prev => [...prev, { role: "ai", content: "Network error occurred." }]);
        } finally {
            setIsLoading(false);
        }
    }

    if (!isOpen) {
        return (
            <button
                onClick={() => setIsOpen(true)}
                className="fixed bottom-6 right-6 z-[100] w-14 h-14 bg-purple-600 hover:bg-purple-500 rounded-full shadow-2xl flex items-center justify-center text-white transition-transform hover:scale-105"
            >
                <Bot size={24} />
                <span className="absolute top-0 right-0 w-3 h-3 bg-red-500 border-2 border-[#0a0a0a] rounded-full animate-pulse"></span>
            </button>
        );
    }

    return (
        <div className={`fixed bottom-6 right-6 z-[100] bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/10 shadow-2xl rounded-2xl flex flex-col overflow-hidden transition-all duration-300 ${isMinimized ? 'w-72 h-14' : 'w-80 h-[450px]'}`}>
            {/* Header */}
            <div className="bg-purple-600 text-white p-3 flex justify-between items-center shrink-0 cursor-pointer" onClick={() => setIsMinimized(!isMinimized)}>
                <div className="flex items-center gap-2">
                    <Bot size={18} />
                    <span className="font-semibold text-sm">CloudSentinel AI</span>
                </div>
                <div className="flex items-center gap-1">
                    <button onClick={(e) => { e.stopPropagation(); setIsMinimized(!isMinimized); }} className="p-1 hover:bg-white/20 rounded">
                        {isMinimized ? <Maximize2 size={14} /> : <Minimize2 size={14} />}
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); setIsOpen(false); }} className="p-1 hover:bg-white/20 rounded">
                        <X size={14} />
                    </button>
                </div>
            </div>

            {/* Chat Area */}
            {!isMinimized && (
                <>
                    <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50 dark:bg-[#050505]">
                        {messages.map((msg, i) => (
                            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-[13px] leading-relaxed shadow-sm ${msg.role === 'user' ? 'bg-blue-600 text-white rounded-br-none' : 'bg-white dark:bg-[#151515] border border-slate-200 dark:border-white/5 text-slate-800 dark:text-slate-200 rounded-bl-none'}`}>
                                    {msg.content}
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
                                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                                placeholder="Ask AI about threats..."
                                className="w-full bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-full pl-4 pr-10 py-2 text-[13px] outline-none focus:ring-1 focus:ring-purple-500 text-slate-900 dark:text-white placeholder:text-slate-500"
                            />
                            <button
                                onClick={handleSend}
                                disabled={!input.trim() || isLoading}
                                className="absolute right-1 w-8 h-8 flex items-center justify-center bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:hover:bg-purple-600 rounded-full text-white transition-colors"
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