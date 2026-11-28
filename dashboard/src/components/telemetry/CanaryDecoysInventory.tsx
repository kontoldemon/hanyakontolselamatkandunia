"use client";

import { useEffect, useState } from "react";
import { Shield } from "lucide-react";

type Decoy = {
    path: string;
    label: string;
    type: string;
    canary: boolean;
    size_bytes: number;
};

type DecoyResponse = {
    ok?: boolean;
    count?: number;
    decoys?: Decoy[];
};

export default function CanaryDecoysInventory() {
    const [decoys, setDecoys] = useState<Decoy[]>([]);
    const [status, setStatus] = useState<"loading" | "live" | "offline">("loading");

    useEffect(() => {
        let cancelled = false;

        async function loadDecoys() {
            try {
                const response = await fetch("/api/cloudsentinel/decoys", { cache: "no-store" });
                const payload = (await response.json().catch(() => ({}))) as DecoyResponse;
                if (cancelled) return;
                if (payload.ok && Array.isArray(payload.decoys)) {
                    setDecoys(payload.decoys);
                    setStatus("live");
                } else {
                    setStatus("offline");
                }
            } catch {
                if (!cancelled) setStatus("offline");
            }
        }

        void loadDecoys();
        const timer = window.setInterval(() => void loadDecoys(), 5000);
        return () => {
            cancelled = true;
            window.clearInterval(timer);
        };
    }, []);

    return (
        <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden">
            <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015] flex items-center justify-between gap-2">
                <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                    <Shield size={14} className="text-emerald-500" /> Canary Decoys &amp; Honey-Tokens
                </h3>
                <div
                    className="flex items-center gap-2 shrink-0"
                    title={status === "offline" ? "Sensor unreachable" : `${decoys.length} Decoys Armed`}
                >
                    <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        {status === "offline" ? "0" : decoys.length}
                    </span>
                    <span className={`w-2 h-2 rounded-full ${status === "live" ? "bg-emerald-500" : status === "loading" ? "bg-amber-500" : "bg-rose-500"}`} />
                </div>
            </div>
            <div className="p-4 sm:p-5">
                {decoys.length === 0 ? (
                    <div className="py-4 text-center text-xs text-slate-500 dark:text-slate-400">
                        {status === "loading" ? "Loading decoy inventory..." : "No decoy files present for the current deception level."}
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 max-h-60 sm:max-h-none overflow-y-auto terminal-scrollbar">
                        {decoys.map((decoy) => (
                            <div
                                key={decoy.path}
                                className="px-3 py-2.5 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] flex flex-col justify-between gap-1.5 min-w-0 transition hover:border-slate-300 dark:hover:border-white/10"
                            >
                                <div className="flex items-center justify-between gap-2 min-w-0">
                                    <span className="text-xs font-semibold text-slate-900 dark:text-white truncate" title={decoy.label}>
                                        {decoy.label}
                                    </span>
                                    <span
                                        title={decoy.canary ? `Canary (${decoy.type})` : `Armed (${decoy.type})`}
                                        aria-label={decoy.canary ? "Canary" : "Armed"}
                                        className={`w-2 h-2 rounded-full shrink-0 ${decoy.canary ? "bg-emerald-500" : "bg-amber-500"}`}
                                    />
                                </div>
                                <div className="flex items-center justify-between gap-2 text-[10.5px] font-mono text-slate-500 dark:text-slate-400 min-w-0">
                                    <span className="truncate" title={decoy.path}>{decoy.path}</span>
                                    <span className="shrink-0 text-slate-400 dark:text-slate-500">{decoy.size_bytes}B</span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
