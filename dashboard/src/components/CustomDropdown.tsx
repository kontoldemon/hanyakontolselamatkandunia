"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";

interface CustomDropdownProps {
    options: { label: string; value: string }[];
    value: string;
    onChange: (value: string) => void;
    className?: string;
}

export default function CustomDropdown({ options, value, onChange, className = "" }: CustomDropdownProps) {
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
        <div className={`relative ${isOpen ? 'z-50' : 'z-10'} ${className}`} ref={dropdownRef}>
            <button 
                type="button"
                className="w-full h-full bg-white dark:bg-[#121212] border border-slate-200 dark:border-white/10 rounded outline-none focus:ring-1 focus:ring-blue-500 flex justify-between items-center text-xs shadow-sm transition-all text-slate-700 dark:text-slate-200 px-2 py-1"
                onClick={() => setIsOpen(!isOpen)}
            >
                <span className="truncate pr-2 font-medium">{selectedLabel}</span>
                <ChevronDown size={14} className={`text-slate-400 transition-transform duration-200 shrink-0 ${isOpen ? 'rotate-180' : ''}`} />
            </button>
            {isOpen && (
                <div className="absolute z-50 w-full mt-1 bg-white dark:bg-[#1a1a1a] border border-slate-200 dark:border-white/10 rounded shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                    <ul className="max-h-60 overflow-y-auto py-1 terminal-scrollbar">
                        {options.map((opt) => (
                            <li 
                                key={opt.value}
                                className={`px-3 py-2 text-xs cursor-pointer flex justify-between items-center transition-colors ${value === opt.value ? 'bg-blue-50/50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 font-bold' : 'hover:bg-slate-50 dark:hover:bg-white/5 text-slate-700 dark:text-slate-300 font-medium'}`}
                                onClick={() => {
                                    onChange(opt.value);
                                    setIsOpen(false);
                                }}
                            >
                                <span className="truncate">{opt.label}</span>
                                {value === opt.value && <Check size={14} className="shrink-0 ml-2" />}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}