"use client";

import { cn } from "@/lib/utils";

export default function ToggleSwitch({
    checked,
    onChange,
    disabled,
}: {
    checked: boolean;
    onChange: (v: boolean) => void;
    disabled?: boolean;
}) {
    return (
        <button
            type="button"
            role="switch"
            aria-checked={checked}
            disabled={disabled}
            onClick={() => onChange(!checked)}
            className={cn(
                "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 outline-none focus:outline-none disabled:opacity-50",
                checked ? "bg-blue-600" : "bg-slate-300 dark:bg-white/15"
            )}
        >
            <span
                className={cn(
                    "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-xs transition duration-200",
                    checked ? "translate-x-4" : "translate-x-0"
                )}
            />
        </button>
    );
}
