"use client";

import { useState } from "react";
import { Search, X } from "lucide-react";
import { List } from "react-window";
import { cn } from "@/lib/utils";
import CustomDropdown from "@/components/ui/CustomDropdown";
import ScrollDownHint from "@/components/ui/ScrollDownHint";
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
        selectedView,
        rowData,
        executeBlockIp,
        clearSelection,
    } = useSessionsViewController();

    const [lastVisibleRow, setLastVisibleRow] = useState(0);

    return (
        <div className="h-full flex flex-col md:flex-row gap-6">
            <div className={cn("flex flex-col h-full md:w-[380px] shrink-0 border border-slate-200 dark:border-white/5 rounded-xl bg-white dark:bg-[#0a0a0a] shadow-sm overflow-hidden", selectedSessionId ? "hidden md:flex" : "flex")}>
                <div className="p-4 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02]">
                    <div className="flex justify-between items-center mb-3">
                        <div className="flex items-center gap-2">
                            <h2 className="font-display text-lg font-bold leading-tight tracking-tight bg-gradient-to-r from-blue-600 to-indigo-500 bg-clip-text text-transparent">Sessions</h2>
                            <span className="text-[10px] font-mono font-medium px-1.5 py-0.5 rounded bg-slate-100 dark:bg-white/[0.06] text-slate-500 dark:text-slate-400">
                                {displayedSessions.length}
                            </span>
                        </div>
                        <CustomDropdown
                            options={[
                                { label: "All Logs", value: "all" },
                                { label: "Active Only", value: "active" },
                            ]}
                            value={filterStatus}
                            onChange={(val) => setFilterStatus(val as "all" | "active")}
                            className="w-28"
                        />
                    </div>
                    <div className="relative flex items-center">
                        <Search size={14} className="absolute left-3 text-slate-400" />
                        <input
                            type="text"
                            placeholder="Search IP, HASSH..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="bg-white dark:bg-[#0f0f0f] border border-slate-200 dark:border-white/10 rounded-lg pl-9 pr-8 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 w-full transition-all shadow-sm"
                        />
                        {searchQuery && (
                            <button
                                onClick={() => setSearchQuery("")}
                                className="absolute right-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                            >
                                <X size={14} />
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
                        <>
                            <List
                                listRef={listRef}
                                rowCount={displayedSessions.length}
                                rowHeight={SESSION_ROW_HEIGHT + SESSION_ROW_GAP}
                                rowProps={rowData}
                                rowComponent={SessionRow}
                                onRowsRendered={(visibleRows) => setLastVisibleRow(visibleRows.stopIndex)}
                                style={{ height: listHeight }}
                                className="terminal-scrollbar pr-1"
                            />
                            <ScrollDownHint
                                visible={
                                    displayedSessions.length * (SESSION_ROW_HEIGHT + SESSION_ROW_GAP) > listHeight + 8 &&
                                    lastVisibleRow < displayedSessions.length - 1
                                }
                                onScrollDown={() => {
                                    const nextIdx = Math.min(displayedSessions.length - 1, lastVisibleRow + 2);
                                    listRef.current?.scrollToRow({ index: nextIdx, align: "end", behavior: "smooth" });
                                }}
                            />
                        </>
                    )}
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
