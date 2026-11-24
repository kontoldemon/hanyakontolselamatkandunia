"use client";

import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface ScrollDownHintProps {
    visible: boolean;
    onScrollDown?: () => void;
    label?: string;
    className?: string;
}

export default function ScrollDownHint({ visible, onScrollDown, label = "More below", className }: ScrollDownHintProps) {
    return (
        <div
            className={cn(
                "pointer-events-none absolute inset-x-0 bottom-0 z-20 flex flex-col items-center justify-end pt-8 pb-2 bg-gradient-to-t from-white via-white/80 to-transparent dark:from-[#0a0a0a] dark:via-[#0a0a0a]/80 dark:to-transparent transition-all duration-300 ease-out",
                visible
                    ? "opacity-100 translate-y-0"
                    : "opacity-0 translate-y-2 pointer-events-none",
                className
            )}
        >
            <button
                type="button"
                onClick={onScrollDown}
                tabIndex={visible ? 0 : -1}
                aria-hidden={!visible}
                className={cn(
                    "font-sans inline-flex items-center gap-1.5 rounded-full border border-slate-200/90 dark:border-white/15 bg-white/90 dark:bg-[#111318]/90 px-3 py-1 text-[10.5px] font-medium text-slate-600 dark:text-slate-300 shadow-sm backdrop-blur-md transition-all duration-300 hover:border-blue-500/40 hover:text-blue-600 dark:hover:text-blue-400 active:scale-95 leading-none cursor-pointer",
                    visible ? "pointer-events-auto scale-100" : "pointer-events-none scale-90"
                )}
            >
                <span>{label}</span>
                <ChevronDown size={11} className={visible ? "animate-bounce" : ""} />
            </button>
        </div>
    );
}
