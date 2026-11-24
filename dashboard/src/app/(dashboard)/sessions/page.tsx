"use client";

import { ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import { List } from "react-window";
import { cn } from "@/lib/utils";
import CustomDropdown from "@/components/ui/CustomDropdown";
import {
    SESSION_ROW_GAP,
    SESSION_ROW_HEIGHT,
    SessionRow,
} from "@/components/sessions/SessionListRow";
import SessionDetailPane from "@/components/sessions/SessionDetailPane";
import { useSessionsViewController } from "@/components/sessions/useSessionsViewController";

export default function SessionsPage() {
    const {
        selectedSessionId,
        searchQuery,
        setSearchQuery,
        filterStatus,
        setFilterStatus,
        blockingIp,
        confirmBlockIp,
        setConfirmBlockIp,
        replayMode,
        setReplayMode,
        listRef,
        listContainerRef,
        listHeight,
        displayedSessions,
        pagedSessions,
        currentPage,
        setCurrentPage,
        totalPages,
        selectedView,
        rowData,
        executeBlockIp,
        clearSelection,
    } = useSessionsViewController();

    return (
        <div className="h-full flex flex-col md:flex-row gap-4">
            <div className={cn("flex flex-col h-full md:w-[305px] lg:w-[315px] shrink-0 border border-slate-200 dark:border-white/5 rounded-xl bg-white dark:bg-[#0a0a0a] shadow-sm overflow-hidden", selectedSessionId ? "hidden md:flex" : "flex")}>
                <div className="p-3.5 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02]">
                    <div className="flex justify-between items-center mb-2.5">
                        <div className="flex items-center gap-2">
                            <h2 className="font-display text-base font-bold leading-tight tracking-tight bg-gradient-to-r from-blue-600 to-indigo-500 bg-clip-text text-transparent">Sessions</h2>
                            <span className="text-[10px] font-mono font-medium px-1.5 py-0.5 rounded bg-slate-100 dark:bg-white/[0.06] text-slate-500 dark:text-slate-400">
                                {displayedSessions.length}
                            </span>
                        </div>
                        <CustomDropdown
                            options={[
                                { label: "All Logs", value: "all" },
                                { label: "Active Only", value: "active" },
                                { label: "Most Attacks", value: "most_attacks" },
                                { label: "Least Attacks", value: "least_attacks" },
                                { label: "High Risk (80+)", value: "high_risk" },
                            ]}
                            value={filterStatus}
                            onChange={(val) => setFilterStatus(val as any)}
                            className="w-32 lg:w-34"
                        />
                    </div>
                    <div className="relative flex items-center">
                        <Search size={13} className="absolute left-2.5 text-slate-400" />
                        <input
                            type="text"
                            placeholder="Search IP, HASSH..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="h-8 bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/10 rounded-lg pl-8 pr-7 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 w-full transition-all shadow-sm text-slate-700 dark:text-slate-200 placeholder:text-slate-400"
                        />
                        {searchQuery && (
                            <button
                                onClick={() => setSearchQuery("")}
                                className="absolute right-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                            >
                                <X size={13} />
                            </button>
                        )}
                    </div>
                </div>

                <div ref={listContainerRef} className="relative flex-1 min-h-0 overflow-hidden p-2">
                    {displayedSessions.length === 0 ? (
                        <div className="p-4 text-center text-xs text-slate-500 dark:text-slate-400">
                            No captured sessions.
                        </div>
                    ) : (
                        <List
                            listRef={listRef}
                            rowCount={pagedSessions.length}
                            rowHeight={SESSION_ROW_HEIGHT + SESSION_ROW_GAP}
                            rowProps={rowData}
                            rowComponent={SessionRow}
                            style={{ height: listHeight }}
                            className="terminal-scrollbar pr-1"
                        />
                    )}
                </div>

                {/* Pagination Controls */}
                <div className="px-3 py-2 border-t border-slate-200 dark:border-white/5 flex items-center justify-between text-xs font-mono text-slate-500 dark:text-slate-400 bg-slate-50/50 dark:bg-white/[0.02] shrink-0">
                    <span className="text-[10.5px]">
                        Page <span className="font-semibold text-slate-800 dark:text-slate-200">{currentPage}</span> of {totalPages}
                        <span className="ml-1 text-[10px] text-slate-400">({displayedSessions.length})</span>
                    </span>
                    <div className="flex items-center gap-1">
                        <button
                            type="button"
                            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                            disabled={currentPage <= 1}
                            className="p-1 rounded hover:bg-slate-200/60 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
                            title="Previous Page"
                            aria-label="Previous Page"
                        >
                            <ChevronLeft size={13} />
                        </button>
                        <button
                            type="button"
                            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                            disabled={currentPage >= totalPages}
                            className="p-1 rounded hover:bg-slate-200/60 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
                            title="Next Page"
                            aria-label="Next Page"
                        >
                            <ChevronRight size={13} />
                        </button>
                    </div>
                </div>
            </div>

            <SessionDetailPane
                selectedSessionId={selectedSessionId}
                selectedView={selectedView}
                replayMode={replayMode}
                onReplayModeChange={setReplayMode}
                onClearSelection={clearSelection}
                blockingIp={blockingIp}
                confirmBlockIp={confirmBlockIp}
                onRequestBlockIp={setConfirmBlockIp}
                onConfirmBlockIp={(ip) => { void executeBlockIp(ip); }}
            />
        </div>
    );
}
