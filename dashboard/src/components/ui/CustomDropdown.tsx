"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { ChevronDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface CustomDropdownProps {
    options: { label: string; value: string }[];
    value: string;
    onChange: (value: string) => void;
    className?: string;
    buttonClassName?: string;
}

type MenuPosition = {
    left: number;
    width: number;
    top?: number;
    bottom?: number;
    maxHeight: number;
};

export default function CustomDropdown({ options, value, onChange, className = "", buttonClassName }: CustomDropdownProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [position, setPosition] = useState<MenuPosition | null>(null);
    const triggerRef = useRef<HTMLButtonElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);
    const selectedLabel = options.find((o) => o.value === value)?.label || value;

    const openMenu = () => {
        const rect = triggerRef.current?.getBoundingClientRect();
        if (!rect) return;
        const spaceBelow = window.innerHeight - rect.bottom - 8;
        const spaceAbove = rect.top - 8;
        const openUp = spaceBelow < 200 && spaceAbove > spaceBelow;
        setPosition({
            left: rect.left,
            width: rect.width,
            maxHeight: Math.min(240, Math.max(120, openUp ? spaceAbove : spaceBelow)),
            ...(openUp
                ? { bottom: window.innerHeight - rect.top + 4 }
                : { top: rect.bottom + 4 }),
        });
        setIsOpen(true);
    };

    useEffect(() => {
        if (!isOpen) return;
        const close = () => setIsOpen(false);
        const onPointerDown = (event: PointerEvent) => {
            const target = event.target as Node;
            if (triggerRef.current?.contains(target) || menuRef.current?.contains(target)) return;
            setIsOpen(false);
        };
        window.addEventListener("scroll", close, true);
        window.addEventListener("resize", close);
        document.addEventListener("pointerdown", onPointerDown);
        return () => {
            window.removeEventListener("scroll", close, true);
            window.removeEventListener("resize", close);
            document.removeEventListener("pointerdown", onPointerDown);
        };
    }, [isOpen]);

    return (
        <div className={cn("relative", className)}>
            <button
                ref={triggerRef}
                type="button"
                aria-haspopup="listbox"
                aria-expanded={isOpen}
                className={cn(
                    "w-full h-10 bg-slate-50/80 dark:bg-white/[0.04] hover:bg-slate-100 dark:hover:bg-white/[0.07] rounded-lg transition-all text-xs text-slate-700 dark:text-slate-300 font-medium px-2.5 py-1 flex justify-between items-center shadow-sm cursor-pointer sm:h-8",
                    "border border-slate-200 dark:border-white/10 outline-none focus:outline-none focus-visible:outline-none",
                    "focus:ring-1 focus:ring-blue-500",
                    isOpen && "ring-1 ring-blue-500",
                    buttonClassName
                )}
                onClick={() => (isOpen ? setIsOpen(false) : openMenu())}
            >
                <span className="truncate pr-1.5">{selectedLabel}</span>
                <ChevronDown size={14} className={cn("text-slate-400 dark:text-slate-500 transition-transform duration-200 shrink-0", isOpen && "rotate-180")} />
            </button>
            {isOpen && position && typeof document !== "undefined" && createPortal(
                <div
                    ref={menuRef}
                    role="listbox"
                    className="fixed z-[90] bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/10 rounded-lg shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150"
                    style={{
                        left: position.left,
                        width: position.width,
                        top: position.top,
                        bottom: position.bottom,
                        maxHeight: position.maxHeight,
                    }}
                >
                    <ul className="overflow-y-auto py-1 terminal-scrollbar" style={{ maxHeight: position.maxHeight }}>
                        {options.map((opt) => (
                            <li
                                key={opt.value}
                                role="option"
                                aria-selected={value === opt.value}
                                className={cn(
                                    "px-3 py-2.5 text-xs cursor-pointer flex justify-between items-center transition-colors sm:py-1.5",
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
                </div>,
                document.body
            )}
        </div>
    );
}
