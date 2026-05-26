"use client";

import TerminalReplay from "@/components/TerminalReplay";
import { Terminal, Clock, Activity, ArrowRight, ShieldAlert, ArrowLeft, Shield, Cpu, Search } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { useCapturedSessions } from "@/lib/liveEvents";

function HighlightText({ text, highlight }: { text: string; highlight: string }) {
    if (!highlight.trim() || !text) {
        return <>{text}</>;
    }
    const regex = new RegExp(`(${highlight})`, "gi");
    const parts = text.split(regex);
    return (
        <>
            {parts.map((part, i) =>
                regex.test(part) ? (
                    <span key={i} className="bg-yellow-200 dark:bg-yellow-900/50 text-slate-900 dark:text-yellow-200 rounded-sm px-0.5 font-bold">
                        {part}
                    </span>
                ) : (
                    <span key={i}>{part}</span>
                )
            )}
        </>
    );
}

// Removed export const dynamic = 'force-static' to let Next.js auto-detect

export default function SessionsPage() {
    const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const sessions = useCapturedSessions();

    const selectedSession = selectedSessionId ? sessions.find(s => s.id === selectedSessionId) : null;

    const filteredSessions = sessions.filter(session => {
        const query = searchQuery.toLowerCase();
        return session.ip.toLowerCase().includes(query) ||
            session.country.toLowerCase().includes(query) ||
            (session.fingerprint && session.fingerprint.toLowerCase().includes(query)) ||
            (session.client && session.client.toLowerCase().includes(query));
    });

    return (
        <div className="space-y-6 relative min-h-screen">
            {/* List View */}
            <div className={cn("space-y-6 transition-all duration-300", selectedSessionId ? "opacity-0 pointer-events-none hidden" : "opacity-100")}>
                <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4">
                    <div>
                        <h2 className="text-2xl font-bold">Captured Sessions</h2>
                        <p className="text-slate-500 dark:text-slate-400">Total Activities Recorded: <span className="text-blue-500 font-mono">{sessions.length}</span></p>
                    </div>
                    <div className="relative">
                        <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input 
                            type="text" 
                            placeholder="Search IP, HASSH, or Client..." 
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 w-full sm:w-[280px] transition-all shadow-sm"
                        />
                    </div>
                </div>

                <div className="grid gap-4">
                    {filteredSessions.length === 0 && (
                        <div className="bg-white dark:bg-[#0a0a0a] p-6 rounded-xl border border-dashed border-slate-300 dark:border-white/10 text-slate-500 dark:text-slate-400">
                            No captured sessions from the sensor yet. Check DigitalOcean admin API and token wiring.
                        </div>
                    )}
                    {filteredSessions.map((session) => (
                        <div key={session.id} className="bg-white dark:bg-[#0a0a0a] p-5 rounded-xl border border-slate-200 dark:border-white/5 hover:border-blue-500/50 transition-all group shadow-sm">
                            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                                <div className="flex items-start gap-4">
                                    <div className="p-3 bg-red-500/10 text-red-500 rounded-lg">
                                        <Terminal size={24} />
                                    </div>
                                    <div>
                                        <div className="flex flex-wrap items-center gap-2 mb-1">
                                            <h3 className="font-bold text-slate-900 dark:text-white font-mono text-lg break-all">
                                                <HighlightText text={session.ip} highlight={searchQuery} />
                                            </h3>
                                            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 dark:bg-white/10 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-white/5 whitespace-nowrap">
                                                <HighlightText text={session.country} highlight={searchQuery} />
                                            </span>
                                            {session.status === 'Active' && (
                                                <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/20 text-green-600 dark:text-green-400 animate-pulse border border-green-500/20 whitespace-nowrap">
                                                    Live
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex flex-wrap items-center gap-4 text-sm text-slate-500 dark:text-slate-400">
                                            <span className="flex items-center gap-1"><Clock size={14} /> {session.duration}</span>
                                            <span className="flex items-center gap-1"><Activity size={14} /> {(session.input ?? []).length} commands</span>
                                            <span className="flex items-center gap-1 font-mono text-xs"><Cpu size={14} /> <HighlightText text={session.client || 'Unknown'} highlight={searchQuery} /></span>
                                            <span className="flex items-center gap-1 font-mono text-xs"><ShieldAlert size={14} /> HASSH: <HighlightText text={session.fingerprint || 'N/A'} highlight={searchQuery} /></span>
                                        </div>
                                    </div>
                                </div>

                                <button
                                    onClick={() => setSelectedSessionId(session.id)}
                                    className="flex items-center justify-center gap-2 px-4 py-2 bg-slate-50 dark:bg-white/5 text-slate-900 dark:text-white rounded-lg hover:bg-blue-600 hover:text-white transition-all font-medium text-sm group-hover:shadow-lg"
                                >
                                    Inspect Session
                                    <ArrowRight size={16} />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Detail View (Overlay) */}
            {selectedSession && (
                <div className="absolute inset-0 bg-slate-50 dark:bg-[#050505] z-10 animate-in fade-in slide-in-from-bottom-4 duration-300">
                    <div className="space-y-6">
                        <button
                            onClick={() => setSelectedSessionId(null)}
                            className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-900 dark:hover:text-white transition-colors text-sm mb-4"
                        >
                            <ArrowLeft size={16} />
                            Back to Sessions
                        </button>

                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            {/* Main: Terminal Replay */}
                            <div className="lg:col-span-2 space-y-4">
                                <h2 className="text-2xl font-bold flex items-center gap-2">
                                    <span className="w-2 h-8 bg-blue-600 rounded-full"></span>
                                    Session Replay
                                </h2>
                                <TerminalReplay lines={selectedSession.input ?? []} />
                            </div>

                            {/* Sidebar: Intelligence */}
                            <div className="space-y-6">
                                <div className="bg-white dark:bg-[#0a0a0a] p-6 rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
                                    <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
                                        <Shield className="text-blue-500" size={20} />
                                        Attacker Profile
                                    </h3>

                                    <div className="space-y-4">
                                        <div>
                                            <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">IP Address</p>
                                            <div className="flex items-center gap-2 mt-1">
                                                <p className="font-mono text-lg font-medium">{selectedSession.ip}</p>
                                                <span className="text-xs bg-slate-100 dark:bg-white/10 px-2 py-0.5 rounded text-slate-500">{selectedSession.country}</span>
                                            </div>
                                        </div>

                                        <div>
                                            <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Client Fingerprint (HASSH)</p>
                                            <p className="font-mono text-sm mt-1 text-slate-600 dark:text-slate-300 break-all">{selectedSession.fingerprint || "N/A"}</p>
                                            <p className="text-xs text-blue-500 mt-1 flex items-center gap-1">
                                                <Cpu size={12} />
                                                Identified as: <span className="font-bold">{selectedSession.client}</span>
                                            </p>
                                        </div>

                                        <div>
                                            <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Timeline</p>
                                            <div className="flex items-center gap-2 mt-1">
                                                <Clock size={14} className="text-slate-400" />
                                                <p className="text-sm">Started at {selectedSession.startTime}</p>
                                            </div>
                                            <p className="text-xs text-slate-500 mt-1">Duration: {selectedSession.duration}</p>
                                        </div>
                                    </div>
                                </div>

                                <div className="bg-red-500/5 border border-red-500/20 p-4 rounded-xl">
                                    <h4 className="text-red-500 font-bold text-sm mb-2 flex items-center gap-2">
                                        <Shield size={16} />
                                        MITRE ATT&CK Detection
                                    </h4>
                                    <ul className="space-y-2">
                                        <li className="text-xs flex justify-between">
                                            <span className="text-slate-600 dark:text-slate-300">T1059.004</span>
                                            <span className="font-mono text-red-400">Command Shell</span>
                                        </li>
                                        <li className="text-xs flex justify-between">
                                            <span className="text-slate-600 dark:text-slate-300">T1105</span>
                                            <span className="font-mono text-red-400">Ingress Tool Transfer</span>
                                        </li>
                                        <li className="text-xs flex justify-between">
                                            <span className="text-slate-600 dark:text-slate-300">T1082</span>
                                            <span className="font-mono text-red-400">System Info Discovery</span>
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
