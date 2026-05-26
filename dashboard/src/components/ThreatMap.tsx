"use client";

import { useTheme } from "next-themes";
import { MouseEvent, useMemo, useState } from "react";
import { MAP_DATA } from "@/lib/mockData";
import { Maximize2, Minimize2 } from "lucide-react";

const TARGET = {
    name: "CloudSentinel HQ",
    lat: 3.1390,
    lng: 101.6869,
};

interface ThreatMapProps {
    onRegionClick?: (region: string | null) => void;
    selectedRegion?: string | null;
}

type TooltipDetails = {
    label: string;
    value: string;
};

type TooltipState = {
    title: string;
    subtitle?: string;
    details?: TooltipDetails[];
    x: number;
    y: number;
};

const WIDTH = 800;
const HEIGHT = 400;

function project(lng: number, lat: number) {
    return {
        x: ((lng + 180) / 360) * WIDTH,
        y: ((90 - lat) / 180) * HEIGHT,
    };
}

function tooltipFor(source: (typeof MAP_DATA)[number], event: MouseEvent<SVGElement>): TooltipState {
    return {
        title: `Attacker Node: ${source.name}`,
        subtitle: "Active Botnet Infrastructure",
        details: [
            { label: "Top IP", value: source.topIp },
            { label: "Dom. TTP", value: source.dominantTtp },
            { label: "HASSH", value: source.topHassh },
        ],
        x: event.clientX,
        y: event.clientY,
    };
}

export default function ThreatMap({ onRegionClick, selectedRegion }: ThreatMapProps = {}) {
    const { theme } = useTheme();
    const [isExpanded, setIsExpanded] = useState(false);
    const [tooltipContent, setTooltipContent] = useState<TooltipState | null>(null);

    const targetPoint = useMemo(() => project(TARGET.lng, TARGET.lat), []);
    const sources = useMemo(() => {
        return MAP_DATA.map((source) => {
            const start = project(source.lng, source.lat);
            const midX = (start.x + targetPoint.x) / 2;
            const midY = (start.y + targetPoint.y) / 2;
            const distance = Math.hypot(targetPoint.x - start.x, targetPoint.y - start.y);
            const path = `M ${start.x},${start.y} Q ${midX},${midY - distance * 0.18} ${targetPoint.x},${targetPoint.y}`;
            return { ...source, point: start, path };
        });
    }, [targetPoint]);

    const land = theme === "dark" ? "#171717" : "#d9e2ec";
    const landStroke = theme === "dark" ? "#303030" : "#f8fafc";
    const ocean = theme === "dark" ? "#050505" : "#f8fafc";

    const selectSource = (name: string) => {
        onRegionClick?.(selectedRegion === name ? null : name);
    };

    return (
        <>
            {isExpanded && (
                <div className="fixed inset-0 z-[90] bg-black/80 backdrop-blur-sm animate-in fade-in duration-200" onClick={() => setIsExpanded(false)} />
            )}
            <div className={isExpanded
                ? "fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-[95vw] h-[90vh] z-[100] bg-slate-50 dark:bg-[#050505] rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col justify-center animate-in zoom-in-95 duration-200"
                : "relative w-full aspect-[2/1] bg-slate-50 dark:bg-[#050505] rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-xl dark:shadow-2xl group transition-all duration-300"}>
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className={`absolute top-4 right-4 z-[80] bg-black/60 hover:bg-black p-2 rounded-lg text-white backdrop-blur border border-white/10 transition-all ${isExpanded ? "opacity-100 scale-100" : "opacity-0 scale-90 group-hover:opacity-100 group-hover:scale-100"}`}
                    title={isExpanded ? "Collapse Map" : "Expand Map"}
                >
                    {isExpanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
                </button>

                <div className={`relative w-full h-full flex ${isExpanded ? "items-center justify-center p-2 md:p-12 mb-12 md:mb-0" : ""}`}>
                    <div className="absolute inset-0 opacity-20 pointer-events-none"
                        style={{
                            backgroundImage: `radial-gradient(${theme === "dark" ? "#333" : "#ccc"} 1px, transparent 1px)`,
                            backgroundSize: "20px 20px",
                        }}>
                    </div>

                    <svg className="relative z-10 w-full h-full" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="CloudSentinel global threat map">
                        <rect width={WIDTH} height={HEIGHT} fill={ocean} />
                        <g opacity={0.5} stroke={theme === "dark" ? "#1f2937" : "#cbd5e1"} strokeWidth="0.5">
                            {Array.from({ length: 9 }).map((_, i) => <line key={`lat-${i}`} x1="0" x2={WIDTH} y1={i * 50} y2={i * 50} />)}
                            {Array.from({ length: 9 }).map((_, i) => <line key={`lng-${i}`} y1="0" y2={HEIGHT} x1={i * 100} x2={i * 100} />)}
                        </g>
                        <g fill={land} stroke={landStroke} strokeWidth="1">
                            <path d="M85 105 C125 70 190 78 232 116 C270 150 252 198 196 208 C140 218 82 178 85 105Z" />
                            <path d="M210 210 C248 208 284 248 264 310 C246 365 190 346 174 296 C158 246 176 216 210 210Z" />
                            <path d="M350 92 C410 58 492 82 520 132 C546 180 486 206 432 190 C374 172 312 132 350 92Z" />
                            <path d="M430 182 C496 174 544 216 526 284 C510 344 450 356 414 310 C382 268 390 198 430 182Z" />
                            <path d="M520 122 C604 88 710 112 724 176 C740 240 650 252 590 220 C536 192 488 148 520 122Z" />
                            <path d="M600 265 C642 248 704 270 716 314 C728 356 668 366 624 348 C584 330 568 286 600 265Z" />
                        </g>

                        {sources.map((source, index) => {
                            const isDimmed = selectedRegion && selectedRegion !== source.name;
                            return (
                                <g key={source.name} opacity={isDimmed ? 0.25 : 1}>
                                    <path
                                        d={source.path}
                                        fill="none"
                                        stroke={source.color}
                                        strokeWidth="2"
                                        strokeLinecap="round"
                                        strokeDasharray="4,4"
                                        style={{ animation: `dash ${2 + index * 0.3}s linear infinite` }}
                                    />
                                    <g
                                        role="button"
                                        tabIndex={0}
                                        onClick={() => selectSource(source.name)}
                                        onMouseEnter={(event) => setTooltipContent(tooltipFor(source, event))}
                                        onMouseMove={(event) => setTooltipContent((previous) => previous ? { ...previous, x: event.clientX, y: event.clientY } : null)}
                                        onMouseLeave={() => setTooltipContent(null)}
                                        className="cursor-pointer"
                                    >
                                        <circle cx={source.point.x} cy={source.point.y} r="8" fill={source.color} opacity="0.2" />
                                        <circle cx={source.point.x} cy={source.point.y} r="4" fill={source.color} className="animate-ping" />
                                        <circle cx={source.point.x} cy={source.point.y} r="3" fill={source.color} />
                                    </g>
                                </g>
                            );
                        })}

                        <g
                            onMouseEnter={(event) => setTooltipContent({ title: TARGET.name, subtitle: "Local Honeypot Target", x: event.clientX, y: event.clientY })}
                            onMouseMove={(event) => setTooltipContent((previous) => previous ? { ...previous, x: event.clientX, y: event.clientY } : null)}
                            onMouseLeave={() => setTooltipContent(null)}
                        >
                            <circle cx={targetPoint.x} cy={targetPoint.y} r="10" fill="rgba(0, 255, 65, 0.25)" stroke="#00ff41" />
                            <circle cx={targetPoint.x} cy={targetPoint.y} r="4" fill="#00ff41" className="animate-pulse" />
                        </g>
                    </svg>



                    <div className={`absolute left-4 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded border border-white/10 flex flex-col gap-1 z-[60] pointer-events-none ${isExpanded ? "top-8 md:top-12 md:left-12" : "top-4"}`}>
                        <span className="text-[10px] text-slate-400 uppercase tracking-widest font-bold">Global Defcon</span>
                        <span className="text-xl font-bold font-mono text-white flex items-center gap-2">
                            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                            ACTIVE
                        </span>
                    </div>

                    {tooltipContent && (
                        <div
                            className="fixed z-[120] bg-slate-900/95 backdrop-blur-md text-slate-100 px-3 py-2 rounded-lg border border-slate-700 shadow-2xl pointer-events-none transform -translate-x-1/2 -translate-y-full mt-[-15px] min-w-[220px] max-w-[280px]"
                            style={{ left: tooltipContent.x, top: tooltipContent.y }}
                        >
                            <div className="flex flex-col gap-0.5 mb-2">
                                <span className="font-bold text-sm text-white">{tooltipContent.title}</span>
                                {tooltipContent.subtitle && <span className="text-[10px] text-red-400 uppercase tracking-widest font-semibold">{tooltipContent.subtitle}</span>}
                            </div>

                            {tooltipContent.details && tooltipContent.details.length > 0 && (
                                <div className="flex flex-col gap-1.5 pt-2 border-t border-slate-700/50">
                                    {tooltipContent.details.map((detail, idx) => (
                                        <div key={idx} className="flex justify-between items-center text-xs">
                                            <span className="text-slate-400 font-medium">{detail.label}:</span>
                                            <span className="font-mono text-blue-300 ml-3 truncate max-w-[120px]">{detail.value}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}
