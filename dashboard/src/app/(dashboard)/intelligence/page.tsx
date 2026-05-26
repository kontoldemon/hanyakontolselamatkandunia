"use client";

import { BrainCircuit, ShieldAlert, Fingerprint } from "lucide-react";
import { useSensorOperations } from "@/lib/liveEvents";

export default function IntelligencePage() {
    const operations = useSensorOperations();
    const attackTypes = operations?.sensor.distribution.data ?? [];
    const totalAttacks = attackTypes.reduce((acc, item) => acc + Number(item.value || 0), 0);
    const graphNodes = operations?.sensor.attackGraph.data?.nodes ?? [];
    const mitreData = graphNodes
        .filter((node) => typeof node === "object" && node !== null && "type" in node && node.type === "technique")
        .map((node) => {
            const record = node as { label?: string };
            return { name: record.label ?? "Technique", count: 1 };
        });
    const sessions = operations?.sensor.sessions.data?.sessions ?? [];
    const fingerprints = sessions
        .filter((session) => session.fingerprint)
        .map((session) => ({
            hash: session.fingerprint,
            client: session.client || "unknown",
            count: session.sessionCount ?? 1,
        }));

    return (
        <div className="space-y-8">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold">Threat Intelligence</h2>
                    <p className="text-slate-500 dark:text-slate-400">TTP Analysis & Fingerprinting</p>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Attack Types Chart */}
                <div className="bg-white dark:bg-[#0a0a0a] p-6 rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
                    <h3 className="font-bold mb-4 flex items-center gap-2">
                        <ShieldAlert className="text-red-500" size={20} />
                        Attack Types Distribution
                    </h3>
                    <div className="h-[300px] w-full relative">
                        <div className="absolute inset-0 flex items-center justify-center">
                            <div className="relative h-44 w-44 rounded-full"
                                style={{
                                    background: totalAttacks > 0 ? `conic-gradient(${attackTypes.map((item, index) => {
                                        const start = attackTypes.slice(0, index).reduce((acc, current) => acc + Number(current.value || 0), 0) / totalAttacks * 100;
                                        const end = start + Number(item.value || 0) / totalAttacks * 100;
                                        return `${item.fill} ${start}% ${end}%`;
                                    }).join(", ")})` : "conic-gradient(#334155 0% 100%)",
                                }}
                            >
                                <div className="absolute inset-10 rounded-full bg-white dark:bg-[#0a0a0a] flex flex-col items-center justify-center">
                                    <span className="text-3xl font-bold text-slate-900 dark:text-white">{totalAttacks}</span>
                                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Total Events</span>
                                </div>
                            </div>
                        </div>
                        <div className="absolute bottom-0 left-0 right-0 grid grid-cols-2 gap-x-4 gap-y-2">
                            {attackTypes.length === 0 && (
                                <div className="col-span-2 text-xs text-slate-500">No live distribution from sensor.</div>
                            )}
                            {attackTypes.map((item) => (
                                <div key={item.name} className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
                                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.fill }} />
                                    <span>{item.name}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* MITRE ATT&CK Chart */}
                <div className="bg-white dark:bg-[#0a0a0a] p-6 rounded-xl border border-slate-200 dark:border-white/5 shadow-sm">
                    <h3 className="font-bold mb-4 flex items-center gap-2">
                        <BrainCircuit className="text-blue-500" size={20} />
                        MITRE ATT&CK Mapping
                    </h3>
                    <div className="h-[300px] w-full space-y-5 pt-2">
                        {mitreData.length === 0 && (
                            <div className="text-sm text-slate-500 dark:text-slate-400">No live MITRE graph nodes from sensor.</div>
                        )}
                        {mitreData.map((item) => {
                            const width = `${Math.round((item.count / Math.max(1, mitreData.length)) * 100)}%`;
                            return (
                                <div key={item.name} className="grid grid-cols-[110px_1fr_44px] items-center gap-3 text-sm">
                                    <span className="text-xs text-slate-500 dark:text-slate-400">{item.name}</span>
                                    <div className="h-3 rounded bg-slate-100 dark:bg-white/10 overflow-hidden">
                                        <div className="h-full rounded bg-blue-500" style={{ width }} />
                                    </div>
                                    <span className="font-mono text-xs text-slate-700 dark:text-slate-300 text-right">{item.count}</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>

            {/* HASSH Fingerprints List */}
            <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-200 dark:border-white/5">
                    <h3 className="font-bold flex items-center gap-2">
                        <Fingerprint className="text-purple-500" size={20} />
                        Top HASSH Fingerprints
                    </h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead className="bg-slate-50 dark:bg-white/5 text-xs text-slate-500">
                            <tr>
                                <th className="px-6 py-3">Fingerprint Hash</th>
                                <th className="px-6 py-3">Client Identification</th>
                                <th className="px-6 py-3">Count</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200 dark:divide-white/5 text-sm">
                            {fingerprints.length === 0 && (
                                <tr>
                                    <td className="px-6 py-4 text-slate-500" colSpan={3}>No live HASSH fingerprints from sensor.</td>
                                </tr>
                            )}
                            {fingerprints.map((item) => (
                                <tr className="hover:bg-slate-50 dark:hover:bg-white/5" key={item.hash}>
                                    <td className="px-6 py-4 font-mono text-slate-600 dark:text-slate-400">{item.hash}</td>
                                    <td className="px-6 py-4 font-medium text-blue-500">{item.client}</td>
                                    <td className="px-6 py-4">{item.count}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
