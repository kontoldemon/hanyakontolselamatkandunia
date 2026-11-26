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
        const timer = window.setInterval(() => void loadDecoys(), 15000);
        return () => {
            cancelled = true;
            window.clearInterval(timer);
        };
    }, []);

    return (
        <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden">
            <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015] flex items-center justify-between">
                <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                    <Shield size={14} className="text-emerald-500" /> Canary Decoys &amp; Honey-Tokens Inventory
                </h3>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 shrink-0">
                    {status === "offline" ? "Sensor unreachable" : `${decoys.length} Decoys Armed`}
                </span>
            </div>
            <div className="divide-y divide-slate-100 dark:divide-white/5">
                {decoys.length === 0 ? (
                    <div className="px-4 py-6 text-center text-xs text-slate-500 dark:text-slate-400">
                        {status === "loading" ? "Loading decoy inventory..." : "No decoy files present for the current deception level."}
                    </div>
                ) : (
                    decoys.map((decoy) => (
                        <div key={decoy.path} className="px-4 py-2.5 sm:px-5 flex items-center justify-between gap-3">
                            <div className="min-w-0 pr-2">
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-semibold text-slate-900 dark:text-white truncate">{decoy.label}</span>
                                    <span className="text-[9.5px] font-mono px-1.5 py-0.2 rounded bg-slate-100 dark:bg-white/[0.05] text-slate-500 dark:text-slate-400 border border-slate-200/60 dark:border-white/10 shrink-0">
                                        {decoy.type}
                                    </span>
                                </div>
                                <p className="text-[11px] font-mono text-slate-500 dark:text-slate-400 truncate mt-0.5">{decoy.path}</p>
                            </div>
                            <div className="flex items-center gap-2.5 shrink-0">
                                <span className="text-[10.5px] text-slate-400 hidden sm:inline">
                                    {decoy.size_bytes} B
                                </span>
                                <span className={`text-[9px] font-mono px-2 py-0.5 rounded-full border ${decoy.canary
                                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                                    : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"}`}>
                                    {decoy.canary ? "Canary" : "Armed"}
                                </span>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
