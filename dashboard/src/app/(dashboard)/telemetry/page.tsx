"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSensorOperations, useSocketTelemetry } from "@/lib/liveEvents";
import SensorPipelinePanel from "@/components/telemetry/SensorPipelinePanel";
import EngineDiagnosticsCard from "@/components/telemetry/EngineDiagnosticsCard";
import CanaryDecoysInventory from "@/components/telemetry/CanaryDecoysInventory";
import SubsystemLatencyGrid from "@/components/telemetry/SubsystemLatencyGrid";
import LiveStreamConsole from "@/components/telemetry/LiveStreamConsole";
import ScrollDownHint from "@/components/ui/ScrollDownHint";

export default function TelemetryPage() {
    const operations = useSensorOperations();
    const socketTelemetry = useSocketTelemetry();

    const scrollRef = useRef<HTMLDivElement>(null);
    const [showScrollDown, setShowScrollDown] = useState(false);

    const handleScroll = useCallback(() => {
        if (!scrollRef.current) return;
        const el = scrollRef.current;
        const dist = el.scrollHeight - (el.scrollTop + el.clientHeight);
        setShowScrollDown(dist > 35);
    }, []);

    const scrollToNext = useCallback(() => {
        if (!scrollRef.current) return;
        scrollRef.current.scrollBy({
            top: 350,
            behavior: "smooth",
        });
    }, []);

    useEffect(() => {
        const timer = setTimeout(() => {
            if (!scrollRef.current) return;
            const el = scrollRef.current;
            setShowScrollDown(el.scrollHeight - el.clientHeight > 35);
        }, 150);
        return () => clearTimeout(timer);
    }, []);

    const upstreamLatency = operations?.telemetry?.upstreamLatencyMs ?? {};
    const latencyRows = [
        { name: "Readiness", value: Number(upstreamLatency.readiness ?? 0) },
        { name: "Metrics", value: Number(upstreamLatency.metrics ?? 0) },
        { name: "Stats", value: Number(upstreamLatency.stats ?? 0) },
        { name: "Sessions", value: Number(upstreamLatency.sessions ?? 0) },
        { name: "Distribution", value: Number(upstreamLatency.distribution ?? 0) },
        { name: "Attack Graph", value: Number(upstreamLatency.attackGraph ?? 0) },
        { name: "Anomaly", value: Number(upstreamLatency.anomaly ?? 0) },
        { name: "LLM", value: Number(upstreamLatency.llm ?? 0) },
    ];

    return (
        <div className="h-full flex flex-col overflow-hidden relative">
            {/* Scrollable Dashboard Body */}
            <div ref={scrollRef} onScroll={handleScroll} className="flex-1 min-h-0 overflow-y-auto terminal-scrollbar pr-1 pt-1">
                <div className="max-w-6xl mx-auto space-y-3.5 pb-1 animate-in fade-in duration-200">
                    {/* 1. Sensor Engine & Storage Pipeline Status */}
                    <SensorPipelinePanel operations={operations} />

                    {/* 2. Containment Engine Diagnostics & MTTB Performance */}
                    <EngineDiagnosticsCard operations={operations} />

                    {/* 3. Canary Decoys & Honey-Tokens Inventory */}
                    <CanaryDecoysInventory />

                    {/* 4. Micro-Service Subsystem Latencies */}
                    <SubsystemLatencyGrid
                        latencyRows={latencyRows}
                        maxLatencyMs={operations?.telemetry?.maxLatencyMs}
                        sampledAt={operations?.telemetry?.sampledAt}
                    />

                    {/* 5. Live WebSocket Stream Debugging Console */}
                    <LiveStreamConsole socketTelemetry={socketTelemetry} />
                </div>
            </div>

            <ScrollDownHint visible={showScrollDown} onScrollDown={scrollToNext} />
        </div>
    );
}
