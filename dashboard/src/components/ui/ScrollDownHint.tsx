"use client";

import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface ScrollDownHintProps {
    visible: boolean;
    onScrollDown?: () => void;
    label?: string;
    showButton?: boolean;
    className?: string;
}

export default function ScrollDownHint({
    visible,
    onScrollDown,
    label,
    showButton = Boolean(label),
    className,
}: ScrollDownHintProps) {
    return (
        <div
            className={cn(
                "pointer-events-none absolute inset-x-0 bottom-0 z-20 flex flex-col items-center justify-end h-16 bg-gradient-to-t from-slate-50 via-slate-50/70 to-transparent dark:from-[#050505] dark:via-[#050505]/70 dark:to-transparent transition-opacity duration-300 ease-out",
                visible ? "opacity-100" : "opacity-0",
                className
            )}
        >
            {showButton && (
                <button
                    type="button"
                    onClick={onScrollDown}
                    tabIndex={visible ? 0 : -1}
                    aria-label={label || "Scroll down"}
                    className={cn(
                        "font-sans mb-2 inline-flex items-center justify-center rounded-full border border-slate-200/90 dark:border-white/15 bg-white/90 dark:bg-[#111318]/90 text-slate-600 dark:text-slate-300 shadow-md backdrop-blur-md transition-all duration-300 hover:border-blue-500/40 hover:text-blue-600 dark:hover:text-blue-400 active:scale-95 cursor-pointer",
                        label ? "gap-1.5 px-3 py-1 text-[10.5px] font-medium leading-none" : "w-7 h-7 p-0",
                        visible ? "pointer-events-auto scale-100" : "pointer-events-none scale-90"
                    )}
                >
                    {label && <span>{label}</span>}
                    <ChevronDown size={label ? 11 : 13} className={cn("text-slate-500 dark:text-slate-400", visible && "animate-bounce")} />
                </button>
            )}
        </div>
    );
}
