"use client";

import { ChevronDown, ChevronUp, Download } from "lucide-react";
import { useState, useCallback, useEffect, useRef } from "react";
import { useAgentCommand } from "@/lib/AgentContext";
import { useSensorOperations } from "@/lib/liveEvents";
import CustomDropdown from "@/components/ui/CustomDropdown";
import ScrollDownHint from "@/components/ui/ScrollDownHint";
import CountryStatsPanel from "@/components/intelligence/CountryStatsPanel";
import TimingHeatmapPanel from "@/components/intelligence/TimingHeatmapPanel";
import NetworkStatsPanel from "@/components/intelligence/NetworkStatsPanel";
import RiskScorePanel from "@/components/intelligence/RiskScorePanel";
import SoarBreakdownPanel from "@/components/intelligence/SoarBreakdownPanel";
import KpiStrip from "@/components/intelligence/KpiStrip";
import TimeSeriesPanel from "@/components/intelligence/TimeSeriesPanel";
import SessionDepthPanel from "@/components/intelligence/SessionDepthPanel";
import AnomalyDetectionPanel from "@/components/intelligence/AnomalyDetectionPanel";
import AttackDistributionPanels from "@/components/intelligence/AttackDistributionPanels";
import {
    CommandsAndPasswordsPanels,
    FingerprintsPanel,
} from "@/components/intelligence/CommandsAndPasswordsPanels";
import {
    TIMELINE_OPTIONS,
    useIntelligenceViewData,
    type GlobalTimeline,
} from "@/components/intelligence/useIntelligenceViewData";

const INITIAL_PANELS: Record<string, boolean> = {
    attackTypes: false,
    mitre: false,
    countries: false,
    timing: false,
    network: false,
    commands: false,
    passwords: false,
    fingerprints: false,
    risk: false,
    soar: false,
    timeSeries: false,
    sessionDepth: false,
    anomaly: false,
};

export default function IntelligencePage() {
    const [commandMode, setCommandMode] = useState<"most" | "least">("most");
    const [commandSearch, setCommandSearch] = useState("");
    const [commandPage, setCommandPage] = useState(1);
    const [timeline, setTimeline] = useState<GlobalTimeline>("all");
    const [panels, setPanels] = useState<Record<string, boolean>>(INITIAL_PANELS);

    const toggleAllPanels = (expand: boolean) => {
        setPanels(Object.fromEntries(Object.keys(INITIAL_PANELS).map((k) => [k, expand])));
    };

    const togglePanel = (panelId: string) => {
        setPanels((prev) => ({
            ...prev,
            [panelId]: !prev[panelId],
        }));
    };

    useAgentCommand("intel.sort", useCallback((v: string) => { setCommandMode(v as "most" | "least"); setCommandPage(1); }, []));
    useAgentCommand("intel.search", useCallback((v: string) => { setCommandSearch(v); setCommandPage(1); }, []));
    useAgentCommand("intel.page", useCallback((v: string) => setCommandPage(Math.max(1, parseInt(v, 10) || 1)), []));

    const {
        stats,
        filteredLiveLogs,
        filteredSessions,
        attackTypes,
        totalAttacks,
        mitreData,
        fingerprints,
        pagedCommands,
        uniqueCommandCount,
        commandCurrentPage,
        commandTotalPages,
        pageSize,
        pageNumbers,
        passwordWords,
        maxPasswordCount,
        kpiValues,
    } = useIntelligenceViewData({ timeline, commandMode, commandSearch, commandPage });

    const operations = useSensorOperations();
    const isAllExpanded = Object.values(panels).every(Boolean);

    const scrollRef = useRef<HTMLDivElement>(null);
    const [showScrollDown, setShowScrollDown] = useState(false);

    const handleScroll = useCallback(() => {
        if (!scrollRef.current) return;
        const el = scrollRef.current;
        const dist = el.scrollHeight - (el.scrollTop + el.clientHeight);
        setShowScrollDown(dist > 35);
    }, []);

    useEffect(() => {
        const timer = setTimeout(() => {
            if (!scrollRef.current) return;
            const el = scrollRef.current;
            setShowScrollDown(el.scrollHeight - el.clientHeight > 35);
        }, 150);
        return () => clearTimeout(timer);
    }, [panels]);

    const downloadIntelligenceReport = useCallback(() => {
        const payload = {
            exportedAt: new Date().toISOString(),
            timeline,
            kpis: kpiValues,
            totalAttacks,
            attackTypes,
            mitreTechniques: mitreData,
            fingerprints,
            source: operations?.source,
            sensor: operations?.sensor,
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `cloudsentinel-intel-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
        document.body.append(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }, [timeline, kpiValues, totalAttacks, attackTypes, mitreData, fingerprints, operations]);

    useEffect(() => {
        const handleExport = () => downloadIntelligenceReport();
        window.addEventListener("agent:export", handleExport);
        return () => window.removeEventListener("agent:export", handleExport);
    }, [downloadIntelligenceReport]);

    return (
        <div className="h-full flex flex-col gap-3 overflow-hidden pt-1 relative">
            <div className="flex flex-wrap justify-between sm:justify-end items-center gap-2 shrink-0 px-1 pt-0.5">
                <CustomDropdown
                    options={TIMELINE_OPTIONS}
                    value={timeline}
                    onChange={(value) => setTimeline(value as GlobalTimeline)}
                    className="w-28"
                />
                <button
                    onClick={downloadIntelligenceReport}
                    className="h-10 sm:h-8 flex items-center gap-1.5 px-3 bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/10 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5 transition-colors shadow-sm"
                    title="Export Intelligence Data"
                >
                    <Download size={14} />
                    <span>Export</span>
                </button>
                <button
                    onClick={() => toggleAllPanels(!isAllExpanded)}
                    className="h-10 sm:h-8 flex items-center gap-1.5 px-3 bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/10 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5 transition-colors shadow-sm"
                >
                    {isAllExpanded ? (
                        <><ChevronUp size={14} /> Collapse All</>
                    ) : (
                        <><ChevronDown size={14} /> Expand All</>
                    )}
                </button>
            </div>

            <KpiStrip
                totalEvents={kpiValues.totalEvents}
                uniqueIps={kpiValues.uniqueIps}
                totalCountries={kpiValues.totalCountries}
                uniqueCommands={kpiValues.uniqueCommands}
                avgRisk={kpiValues.avgRisk}
                blockRate={kpiValues.blockRate}
            />

            <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto terminal-scrollbar min-h-0 pb-1 pr-2 space-y-2.5">
                <AttackDistributionPanels
                    attackTypesExpanded={panels.attackTypes}
                    mitreExpanded={panels.mitre}
                    onToggleAttackTypes={() => togglePanel("attackTypes")}
                    onToggleMitre={() => togglePanel("mitre")}
                    attackTypes={attackTypes}
                    totalAttacks={totalAttacks}
                    mitreData={mitreData}
                />

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-2.5 items-start">
                    <CountryStatsPanel expanded={panels.countries} onToggle={() => togglePanel("countries")} countries={stats.countries} />
                    <TimingHeatmapPanel expanded={panels.timing} onToggle={() => togglePanel("timing")} heatmap={stats.heatmap} />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-2.5 items-start">
                    <NetworkStatsPanel expanded={panels.network} onToggle={() => togglePanel("network")} isps={stats.isps} />
                    <FingerprintsPanel expanded={panels.fingerprints} onToggle={() => togglePanel("fingerprints")} fingerprints={fingerprints} />
                </div>

                <CommandsAndPasswordsPanels
                    commandsExpanded={panels.commands}
                    passwordsExpanded={panels.passwords}
                    onToggleCommands={() => togglePanel("commands")}
                    onTogglePasswords={() => togglePanel("passwords")}
                    commandMode={commandMode}
                    onCommandModeChange={(mode) => { setCommandMode(mode); setCommandPage(1); }}
                    commandSearch={commandSearch}
                    onCommandSearchChange={(search) => { setCommandSearch(search); setCommandPage(1); }}
                    pagedCommands={pagedCommands}
                    uniqueCommandCount={uniqueCommandCount}
                    commandCurrentPage={commandCurrentPage}
                    commandTotalPages={commandTotalPages}
                    pageSize={pageSize}
                    pageNumbers={pageNumbers}
                    onCommandPageChange={setCommandPage}
                    passwordWords={passwordWords}
                    maxPasswordCount={maxPasswordCount}
                />

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-2.5 items-start">
                    <RiskScorePanel expanded={panels.risk} onToggle={() => togglePanel("risk")} risk={stats.risk} />
                    <SoarBreakdownPanel expanded={panels.soar} onToggle={() => togglePanel("soar")} soar={stats.soar} />
                </div>

                <div className="grid grid-cols-1 gap-2.5 items-start">
                    <TimeSeriesPanel
                        expanded={panels.timeSeries}
                        onToggle={() => togglePanel("timeSeries")}
                        timelineWindow={timeline}
                    />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-2.5 items-start">
                    <SessionDepthPanel
                        expanded={panels.sessionDepth}
                        onToggle={() => togglePanel("sessionDepth")}
                        sessions={filteredSessions}
                    />
                    <AnomalyDetectionPanel
                        expanded={panels.anomaly}
                        onToggle={() => togglePanel("anomaly")}
                        logs={filteredLiveLogs}
                        anomaly={operations?.sensor?.anomaly}
                    />
                </div>
            </div>

            <ScrollDownHint visible={showScrollDown} />
        </div>
    );
}
