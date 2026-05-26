"use client";

import { useLiveThreatLogs } from "@/lib/liveEvents";
import { Globe, Shield } from "lucide-react";
import clsx from "clsx";
import { useEffect, useRef } from "react";

interface AttackLogProps {
    selectedRegion?: string | null;
}

export default function AttackLog({ selectedRegion }: AttackLogProps = {}) {
    const COUNTRY_MAP: Record<string, string> = {
        "China": "CN",
        "Russia": "RU",
        "Brazil": "BR",
        "United States of America": "US",
        "USA": "US",
        "Iran": "IR",
        "Vietnam": "VN"
    };

    const targetCode = selectedRegion ? COUNTRY_MAP[selectedRegion] : null;
    const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});
    const threatLogs = useLiveThreatLogs();

    useEffect(() => {
        if (targetCode) {
            // Find the first log that matches the target code
            const firstMatch = threatLogs.find(log => log.country === targetCode);
            if (firstMatch && itemRefs.current[firstMatch.id]) {
                const el = itemRefs.current[firstMatch.id];
                if (el) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        }
    }, [targetCode, threatLogs]);

    return (
        <div className="h-full overflow-y-auto terminal-scrollbar pr-2 min-h-0 scroll-smooth">
            <div className="space-y-2 pb-4">
                {threatLogs?.map((log) => {
                    const isSelected = targetCode && log.country === targetCode;
                    const isDimmed = targetCode && log.country !== targetCode;
                    return (
                        <div 
                            key={log.id} 
                            ref={(el) => { itemRefs.current[log.id] = el; }}
                            className={clsx(
                            "p-3 bg-white dark:bg-white/5 rounded-lg transition-all duration-300 cursor-default group",
                            isSelected ? "border-2 border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.15)] bg-blue-50/50 dark:bg-blue-500/10" : "border border-slate-200 dark:border-white/5 hover:bg-slate-50 dark:hover:bg-white/10",
                            isDimmed ? "opacity-30 grayscale" : "opacity-100"
                        )}>
                            <div className="flex justify-between items-start mb-1">
                            <span className="text-[10px] font-mono text-slate-400">{log.timestamp}</span>
                            <div className="flex items-center gap-2">
                                {log.action === "Blocked" && (
                                    <span className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded border border-red-500/30 text-red-500 font-bold bg-red-500/10">
                                        <Shield size={10} />
                                        BLOCKED {log.timeToBlock}
                                    </span>
                                )}
                                <span className={clsx(
                                    "text-[10px] px-1.5 rounded font-bold",
                                    log.type === 'SSH_AUTH_FAIL' ? "bg-red-500/20 text-red-500" :
                                        log.type === 'COMMAND_EXEC' ? "bg-orange-500/20 text-orange-500" :
                                            "bg-blue-500/20 text-blue-500"
                                )}>{log.type}</span>
                            </div>
                        </div>
                        <div className="flex items-center justify-between mt-1">
                            <div className="flex items-center gap-2 text-xs font-mono text-slate-700 dark:text-slate-300">
                                <Globe size={12} className="text-slate-500" />
                                <span>{log.ip}</span>
                                <span className="opacity-50">({log.country})</span>
                            </div>
                            {log.mitreId && (
                                <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-200 dark:bg-white/10 text-slate-600 dark:text-slate-400 font-mono">
                                    {log.mitreId}
                               </span>
                            )}
                        </div>
                            <div className="mt-2 text-xs font-mono text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-black/30 p-1.5 rounded truncate">
                                $ {log.payload}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
