"use client";

import { BrainCircuit, ShieldAlert, Fingerprint } from "lucide-react";
import { useLiveThreatLogs, useSensorOperations } from "@/lib/liveEvents";
import { useState } from "react";

export default function IntelligencePage() {
    const [commandMode, setCommandMode] = useState<"most" | "least">("most");
    const [commandSearch, setCommandSearch] = useState("");
    const [commandPage, setCommandPage] = useState(1);
    const [responseModeFilter, setResponseModeFilter] = useState("all");
    const PAGE_SIZE = 10;

    const operations = useSensorOperations();
    const liveLogs = useLiveThreatLogs();
    const attackTypes = operations?.sensor.distribution.data ?? [];
    const totalAttacks = attackTypes.reduce((acc, item) => acc + Number(item.value || 0), 0);
    const graphNodes = operations?.sensor.attackGraph.data?.nodes ?? [];
    const mitreFromGraph = graphNodes
        .filter((node) => typeof node === "object" && node !== null && "type" in node && node.type === "technique")
        .map((node) => {
            const record = node as { label?: string };
            return record.label ?? "Technique";
        });
    const sessions = operations?.sensor.sessions.data?.sessions ?? [];
    const mitreCounts = new Map<string, number>();
    for (const tech of mitreFromGraph) {
        mitreCounts.set(tech, (mitreCounts.get(tech) ?? 0) + 1);
    }
    for (const session of sessions) {
        for (const tech of session.mitreTechniques ?? []) {
            mitreCounts.set(tech, (mitreCounts.get(tech) ?? 0) + 1);
        }
    }
    for (const log of liveLogs) {
        for (const tech of log.mitreTechniques ?? []) {
            mitreCounts.set(tech, (mitreCounts.get(tech) ?? 0) + 1);
        }
    }
    const mitreData = [...mitreCounts.entries()]
        .map(([name, count]) => ({ name, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 14);

    const fingerprintsMap = new Map<string, { hash: string; client: string; count: number }>();
    for (const session of sessions) {
        const hash = (session.fingerprint ?? "").trim();
        if (!hash) {
            continue;
        }
        const current = fingerprintsMap.get(hash) ?? { hash, client: session.client || "unknown", count: 0 };
        current.count += session.sessionCount ?? 1;
        if (!current.client || current.client === "unknown") {
            current.client = session.client || "unknown";
        }
        fingerprintsMap.set(hash, current);
    }
    for (const log of liveLogs) {
        const hash = (log.hassh ?? "").trim();
        if (!hash) {
            continue;
        }
        const current = fingerprintsMap.get(hash) ?? { hash, client: "unknown", count: 0 };
        current.count += 1;
        fingerprintsMap.set(hash, current);
    }
    const fingerprints = [...fingerprintsMap.values()].sort((a, b) => b.count - a.count).slice(0, 20);

    const commandCounts = new Map<string, number>();
    const incrementCommand = (raw: string) => {
        const cmd = raw.trim();
        if (!cmd) {
            return;
        }
        if (cmd.startsWith("cloudsentinel.")) {
            return;
        }
        if (cmd.includes("[redacted]")) {
            return;
        }
        commandCounts.set(cmd, (commandCounts.get(cmd) ?? 0) + 1);
    };
    for (const session of sessions) {
        for (const cmd of session.input ?? []) {
            incrementCommand(cmd);
        }
    }
    for (const log of liveLogs) {
        if (log.role === "attacker") {
            incrementCommand(log.payload ?? "");
        }
    }
    const topCommands = [...commandCounts.entries()]
        .map(([command, count]) => ({ command, count }))
        .sort((a, b) => (b.count - a.count) || a.command.localeCompare(b.command));
    const leastCommands = [...commandCounts.entries()]
        .map(([command, count]) => ({ command, count }))
        .sort((a, b) => (a.count - b.count) || a.command.localeCompare(b.command));
    const uniqueCommandCount = commandCounts.size;
    const responseModeTotals = new Map<string, number>();
    for (const log of liveLogs) {
        if (log.role !== "honeypot") {
            continue;
        }
        const mode = (log.responseMode || "deterministic").trim().toLowerCase() || "deterministic";
        responseModeTotals.set(mode, (responseModeTotals.get(mode) ?? 0) + 1);
    }
    const responseModeRows = [...responseModeTotals.entries()]
        .map(([mode, count]) => ({ mode, count }))
        .sort((a, b) => b.count - a.count);
    const filteredResponseModeRows = responseModeFilter === "all"
        ? responseModeRows
        : responseModeRows.filter((item) => item.mode === responseModeFilter);
    const sourceCommands = commandMode === "most" ? topCommands : leastCommands;
    const commandQuery = commandSearch.trim().toLowerCase();
    const commandRows = sourceCommands
        .filter((item) => {
            if (!commandQuery) {
                return true;
            }
            return item.command.toLowerCase().includes(commandQuery);
        });
    const commandTotalPages = Math.max(1, Math.ceil(commandRows.length / PAGE_SIZE));
    const commandCurrentPage = Math.min(commandPage, commandTotalPages);
    const pagedCommands = commandRows.slice((commandCurrentPage - 1) * PAGE_SIZE, commandCurrentPage * PAGE_SIZE);
    const pageNumbers = Array.from({ length: commandTotalPages }, (_, index) => index + 1);

    return (
        <div className="h-full flex flex-col gap-6">
            <div className="flex justify-between items-center shrink-0">
                <div>
                    <h2 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-500 bg-clip-text text-transparent">Threat Intelligence</h2>
                    <p className="text-slate-500 text-xs mt-0.5">TTP Analysis & Fingerprinting</p>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 shrink-0">
                {/* Attack Types Chart */}
                <div className="bg-white dark:bg-[#0a0a0a] p-4 rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
                    <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
                        <ShieldAlert className="text-red-500" size={16} />
                        Attack Types Distribution
                    </h3>
                    <div className="h-[200px] w-full relative">
                        <div className="absolute inset-0 flex items-center justify-center">
                            <div className="relative h-32 w-32 rounded-full"
                                style={{
                                    background: totalAttacks > 0 ? `conic-gradient(${attackTypes.map((item, index) => {
                                        const start = attackTypes.slice(0, index).reduce((acc, current) => acc + Number(current.value || 0), 0) / totalAttacks * 100;
                                        const end = start + Number(item.value || 0) / totalAttacks * 100;
                                        return `${item.fill} ${start}% ${end}%`;
                                    }).join(", ")})` : "conic-gradient(#334155 0% 100%)",
                                }}
                            >
                                <div className="absolute inset-6 rounded-full bg-white dark:bg-[#0a0a0a] flex flex-col items-center justify-center">
                                    <span className="text-xl font-bold text-slate-900 dark:text-white">{totalAttacks}</span>
                                    <span className="text-[10px] font-medium text-slate-500">Events</span>
                                </div>
                            </div>
                        </div>
                        <div className="absolute bottom-0 left-0 right-0 flex flex-wrap justify-center gap-x-4 gap-y-1">
                            {attackTypes.length === 0 && (
                                <div className="text-[11px] text-slate-500">No live distribution from sensor.</div>
                            )}
                            {attackTypes.map((item) => (
                                <div key={item.name} className="flex items-center gap-1.5 text-[11px] text-slate-600 dark:text-slate-400">
                                    <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: item.fill }} />
                                    <span>{item.name}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* MITRE ATT&CK Chart */}
                <div className="bg-white dark:bg-[#0a0a0a] p-4 rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
                    <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
                        <BrainCircuit className="text-blue-500" size={16} />
                        MITRE ATT&CK Mapping
                    </h3>
                    <div className="h-[200px] w-full space-y-3 pt-1 overflow-y-auto pr-2 terminal-scrollbar">
                        {mitreData.length === 0 && (
                            <div className="text-xs text-slate-500">No live MITRE graph nodes from sensor.</div>
                        )}
                        {mitreData.map((item) => {
                            const width = `${Math.round((item.count / Math.max(1, mitreData.length)) * 100)}%`;
                            return (
                                <div key={item.name} className="grid grid-cols-[100px_1fr_30px] items-center gap-2 text-xs">
                                    <span className="text-[10px] text-slate-500 truncate" title={item.name}>{item.name}</span>
                                    <div className="h-2 rounded bg-slate-100 dark:bg-white/10 overflow-hidden">
                                        <div className="h-full rounded bg-blue-500" style={{ width }} />
                                    </div>
                                    <span className="font-mono text-[10px] text-slate-700 dark:text-slate-300 text-right">{item.count}</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>

            {/* Bottom Section: Tables side-by-side */}
            <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-2 gap-6">
                
                {/* Attacker Command Table */}
                <div className="flex flex-col bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm overflow-hidden">
                    <div className="p-4 border-b border-slate-200 dark:border-white/5 shrink-0 bg-slate-50/50 dark:bg-white/[0.02] space-y-3">
                        <div className="flex items-center justify-between gap-3">
                            <h3 className="font-semibold text-sm flex items-center gap-2">
                                <ShieldAlert className="text-amber-500" size={16} />
                                Attacker Commands
                            </h3>
                            <span className="text-[10px] font-mono text-amber-600 bg-amber-500/10 px-2 py-0.5 rounded">{uniqueCommandCount} unique</span>
                        </div>
                        <div className="flex gap-2 items-center">
                            <div className="flex rounded border border-slate-200 dark:border-white/10 overflow-hidden shrink-0">
                                <button onClick={() => { setCommandMode("most"); setCommandPage(1); }} className={`px-2 py-1 text-[10px] font-medium ${commandMode === "most" ? "bg-blue-600 text-white" : "bg-white dark:bg-[#0f0f0f] text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5"}`}>Most</button>
                                <button onClick={() => { setCommandMode("least"); setCommandPage(1); }} className={`px-2 py-1 text-[10px] font-medium border-l border-slate-200 dark:border-white/10 ${commandMode === "least" ? "bg-blue-600 text-white" : "bg-white dark:bg-[#0f0f0f] text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5"}`}>Least</button>
                            </div>
                            <input type="text" value={commandSearch} onChange={(e) => { setCommandSearch(e.target.value); setCommandPage(1); }} placeholder="Search..." className="w-full bg-white dark:bg-[#0f0f0f] border border-slate-200 dark:border-white/10 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
                        </div>
                    </div>
                    
                    <div className="flex-1 overflow-y-auto">
                        <table className="w-full text-left">
                            <thead className="bg-slate-50 dark:bg-white/5 text-[10px] text-slate-500 sticky top-0 backdrop-blur-md">
                                <tr>
                                    <th className="px-4 py-2 font-medium w-12">No.</th>
                                    <th className="px-4 py-2 font-medium">Command</th>
                                    <th className="px-4 py-2 font-medium w-16 text-right">Freq</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-white/5 text-xs">
                                {pagedCommands.length === 0 && (
                                    <tr><td className="px-4 py-3 text-slate-500 text-center" colSpan={3}>No commands yet.</td></tr>
                                )}
                                {pagedCommands.map((item, index) => (
                                    <tr className="hover:bg-slate-50 dark:hover:bg-white/5" key={`${commandMode}-${item.command}`}>
                                        <td className="px-4 py-2 text-slate-400 font-mono">{(commandCurrentPage - 1) * PAGE_SIZE + index + 1}</td>
                                        <td className="px-4 py-2 text-slate-700 dark:text-slate-300 font-mono break-all leading-tight">{item.command}</td>
                                        <td className="px-4 py-2 text-slate-500 font-mono text-right">{item.count}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    
                    <div className="p-2 border-t border-slate-200 dark:border-white/5 shrink-0 bg-slate-50/50 dark:bg-white/[0.02] flex items-center justify-between">
                        <span className="text-[10px] text-slate-500">Page {commandCurrentPage} of {commandTotalPages}</span>
                        <div className="flex gap-1">
                            {pageNumbers.map(page => (
                                <button key={page} onClick={() => setCommandPage(page)} className={`w-5 h-5 rounded text-[10px] font-medium ${page === commandCurrentPage ? "bg-blue-600 text-white" : "bg-white dark:bg-[#0f0f0f] border border-slate-200 dark:border-white/10 text-slate-500"}`}>{page}</button>
                            ))}
                        </div>
                    </div>
                </div>

                {/* HASSH Fingerprints Table */}
                <div className="flex flex-col bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm overflow-hidden">
                    <div className="p-4 border-b border-slate-200 dark:border-white/5 shrink-0 bg-slate-50/50 dark:bg-white/[0.02]">
                        <h3 className="font-semibold text-sm flex items-center gap-2">
                            <Fingerprint className="text-purple-500" size={16} />
                            HASSH Fingerprints
                        </h3>
                    </div>
                    <div className="flex-1 overflow-y-auto">
                        <table className="w-full text-left">
                            <thead className="bg-slate-50 dark:bg-white/5 text-[10px] text-slate-500 sticky top-0 backdrop-blur-md">
                                <tr>
                                    <th className="px-4 py-2 font-medium">Hash</th>
                                    <th className="px-4 py-2 font-medium">Client Info</th>
                                    <th className="px-4 py-2 font-medium w-16 text-right">Count</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-white/5 text-xs">
                                {fingerprints.length === 0 && (
                                    <tr><td className="px-4 py-3 text-slate-500 text-center" colSpan={3}>No fingerprints captured.</td></tr>
                                )}
                                {fingerprints.map((item) => (
                                    <tr className="hover:bg-slate-50 dark:hover:bg-white/5" key={item.hash}>
                                        <td className="px-4 py-2 font-mono text-[10px] text-slate-500">{item.hash}</td>
                                        <td className="px-4 py-2 text-blue-500 font-mono text-[10px] truncate max-w-[120px]" title={item.client}>{item.client}</td>
                                        <td className="px-4 py-2 text-slate-500 font-mono text-right">{item.count}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

            </div>
        </div>
    );
}
