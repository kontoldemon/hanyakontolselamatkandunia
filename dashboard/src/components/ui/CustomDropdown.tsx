"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface CustomDropdownProps {
    options: { label: string; value: string }[];
    value: string;
    onChange: (value: string) => void;
    className?: string;
    buttonClassName?: string;
}

export default function CustomDropdown({ options, value, onChange, className = "", buttonClassName }: CustomDropdownProps) {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const selectedLabel = options.find((o) => o.value === value)?.label || value;

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    return (
        <div className={cn("relative", isOpen ? "z-[80]" : "z-10", className)} ref={dropdownRef}>
            <button
                type="button"
                className={cn(
                    "w-full h-8 bg-slate-50/80 dark:bg-white/[0.04] hover:bg-slate-100 dark:hover:bg-white/[0.07] rounded-lg transition-all text-xs text-slate-700 dark:text-slate-300 font-medium px-2.5 py-1 flex justify-between items-center shadow-sm cursor-pointer",
                    "border border-slate-200 dark:border-white/10 outline-none focus:outline-none focus-visible:outline-none",
                    "focus:ring-1 focus:ring-blue-500",
                    isOpen && "ring-1 ring-blue-500",
                    buttonClassName
                )}
                onClick={() => setIsOpen(!isOpen)}
            >
                <span className="truncate pr-1.5">{selectedLabel}</span>
                <ChevronDown size={14} className={cn("text-slate-400 dark:text-slate-500 transition-transform duration-200 shrink-0", isOpen && "rotate-180")} />
            </button>
            {isOpen && (
                <div className="absolute right-0 z-[90] min-w-full mt-1 bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/10 rounded-lg shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
                    <ul className="max-h-60 overflow-y-auto py-1 terminal-scrollbar">
                        {options.map((opt) => (
                            <li
                                key={opt.value}
                                className={cn(
                                    "px-3 py-1.5 text-xs cursor-pointer flex justify-between items-center transition-colors",
                                    value === opt.value
                                        ? "bg-blue-50/70 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold"
                                        : "hover:bg-slate-50 dark:hover:bg-white/5 text-slate-700 dark:text-slate-300 font-medium"
                                )}
                                onClick={() => {
                                    onChange(opt.value);
                                    setIsOpen(false);
                                }}
                            >
                                <span className="truncate">{opt.label}</span>
                                {value === opt.value && <Check size={13} className="shrink-0 ml-2" />}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}
