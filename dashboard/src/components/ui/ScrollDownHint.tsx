"use client";

import { ChevronDown } from "lucide-react";

interface ScrollDownHintProps {
    visible: boolean;
    onScrollDown?: () => void;
    label?: string;
}

export default function ScrollDownHint({ visible, onScrollDown, label = "More below" }: ScrollDownHintProps) {
    if (!visible) return null;

    return (
        <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex flex-col items-center justify-end pt-8 pb-2 bg-gradient-to-t from-white via-white/80 to-transparent dark:from-[#0a0a0a] dark:via-[#0a0a0a]/80 dark:to-transparent">
            <button
                type="button"
                onClick={onScrollDown}
                className="pointer-events-auto font-sans inline-flex items-center gap-1.5 rounded-full border border-slate-200/90 dark:border-white/15 bg-white/90 dark:bg-[#111318]/90 px-3 py-1 text-[10.5px] font-medium text-slate-600 dark:text-slate-300 shadow-sm backdrop-blur-md transition hover:border-blue-500/40 hover:text-blue-600 dark:hover:text-blue-400 active:scale-95 leading-none"
            >
                <span>{label}</span>
                <ChevronDown size={11} className="animate-bounce" />
            </button>
        </div>
    );
}
