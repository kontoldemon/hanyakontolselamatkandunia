"use client";

import { ChevronRight, Maximize2, Minimize2 } from "lucide-react";
import { ReactNode, ComponentType, useState, useEffect } from "react";
import { createPortal } from "react-dom";

interface CollapsiblePanelProps {
    expanded: boolean;
    onToggle: () => void;
    icon: ComponentType<{ size: number; className?: string }>;
    iconColor: string;
    title: string;
    summary: string;
    children: ReactNode;
}

export default function CollapsiblePanel({
    expanded,
    onToggle,
    icon: Icon,
    iconColor,
    title,
    summary,
    children,
}: CollapsiblePanelProps) {
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    const toggleFullscreen = (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsFullscreen(!isFullscreen);
        // Expand if going fullscreen and not expanded
        if (!isFullscreen && !expanded) {
            onToggle();
        }
    };

    const content = (
        <div className={`bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm flex flex-col ${isFullscreen ? 'fixed inset-4 z-50 shadow-2xl h-full' : 'overflow-hidden'}`}>
            <button
                type="button"
                onClick={isFullscreen ? undefined : onToggle}
                className={`w-full px-4 py-3 flex items-center justify-between gap-2 hover:bg-slate-50/50 dark:hover:bg-white/[0.02] transition-colors ${isFullscreen ? 'cursor-default' : 'cursor-pointer'}`}
            >
                <div className="flex items-center gap-2 min-w-0">
                    <Icon size={15} className={`${iconColor} shrink-0`} />
                    <span className="font-semibold text-sm text-slate-900 dark:text-white truncate">{title}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                    <span className="text-[10px] text-slate-500 font-mono hidden sm:inline">{summary}</span>
                    <button 
                        onClick={toggleFullscreen}
                        className="text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
                        title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
                    >
                        {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
                    </button>
                    {!isFullscreen && (
                        <ChevronRight
                            size={14}
                            className={`text-slate-400 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`}
                        />
                    )}
                </div>
            </button>
            <div
                className={`grid transition-[grid-template-rows] duration-300 ease-in-out ${isFullscreen ? 'flex-1 overflow-hidden' : ''}`}
                style={isFullscreen ? { gridTemplateRows: "1fr" } : { gridTemplateRows: expanded ? "1fr" : "0fr" }}
            >
                <div className={`min-h-0 ${isFullscreen ? 'h-full flex flex-col' : 'overflow-hidden'}`}>
                    <div data-fullscreen={isFullscreen} className={`px-4 pb-4 border-t border-slate-100 dark:border-white/5 pt-3 group/fs ${isFullscreen ? 'flex-1 overflow-auto' : ''}`}>
                        {children}
                    </div>
                </div>
            </div>
        </div>
    );

    if (isFullscreen && mounted) {
        return (
            <>
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm h-12" />
                {createPortal(
                    <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm p-4 md:p-12">
                        <div className="bg-white dark:bg-[#0a0a0a] rounded-xl shadow-2xl h-full w-full flex flex-col border border-white/10 relative overflow-hidden">
                            {content}
                        </div>
                    </div>,
                    document.body
                )}
            </>
        );
    }

    return content;
}
