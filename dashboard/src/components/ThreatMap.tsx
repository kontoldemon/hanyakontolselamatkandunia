"use client";

import { useTheme } from "next-themes";
import { MouseEvent, useEffect, useMemo, useState } from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import { geoEqualEarth, geoGraticule, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import { ThreatLog, useLiveThreatLogs } from "@/lib/liveEvents";

const TARGET = {
    name: "CloudSentinel HQ",
    lat: 3.1390,
    lng: 101.6869,
};

interface ThreatMapProps {
    onRegionClick?: (region: string | null) => void;
    selectedRegion?: string | null;
    underAttack?: boolean;
    threatLogs?: ThreatLog[];
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
const COUNTRY_COORDS: Record<string, { name: string; lat: number; lng: number; color: string }> = {
    BR: { name: "Brazil", lat: -14.235, lng: -51.9253, color: "#eab308" },
    CN: { name: "China", lat: 35.8617, lng: 104.1954, color: "#ef4444" },
    DE: { name: "Germany", lat: 51.1657, lng: 10.4515, color: "#38bdf8" },
    ID: { name: "Indonesia", lat: -0.7893, lng: 113.9213, color: "#22c55e" },
    IN: { name: "India", lat: 20.5937, lng: 78.9629, color: "#f97316" },
    IR: { name: "Iran", lat: 32.4279, lng: 53.688, color: "#a855f7" },
    MY: { name: "Malaysia", lat: 4.2105, lng: 101.9758, color: "#14b8a6" },
    RU: { name: "Russia", lat: 61.524, lng: 105.3188, color: "#f97316" },
    SG: { name: "Singapore", lat: 1.3521, lng: 103.8198, color: "#06b6d4" },
    TH: { name: "Thailand", lat: 15.87, lng: 100.9925, color: "#84cc16" },
    US: { name: "United States of America", lat: 37.0902, lng: -95.7129, color: "#3b82f6" },
    VN: { name: "Vietnam", lat: 14.0583, lng: 108.2772, color: "#ec4899" },
};

type CountryFeature = {
    type: "Feature";
    properties?: { name?: string };
};

type Source = {
    name: string;
    lat: number;
    lng: number;
    count: number;
    color: string;
    topIp: string;
    dominantTtp: string;
    topHassh: string;
};

function tooltipFor(source: Source, event: MouseEvent<SVGElement>): TooltipState {
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

export default function ThreatMap({ onRegionClick, selectedRegion, underAttack = false, threatLogs: externalLogs }: ThreatMapProps = {}) {
    const { theme } = useTheme();
    const [isExpanded, setIsExpanded] = useState(false);
    const [tooltipContent, setTooltipContent] = useState<TooltipState | null>(null);
    const [countries, setCountries] = useState<CountryFeature[]>([]);
    const liveLogs = useLiveThreatLogs(!externalLogs);
    const threatLogs = externalLogs ?? liveLogs;

    useEffect(() => {
        let cancelled = false;
        fetch("/world-atlas.json")
            .then((response) => response.json())
            .then((topology) => {
                if (cancelled) {
                    return;
                }
                const collection = feature(topology, topology.objects.countries) as unknown as {
                    features: CountryFeature[];
                };
                setCountries(collection.features);
            })
            .catch(() => setCountries([]));

        return () => {
            cancelled = true;
        };
    }, []);

    const projection = useMemo(
        () =>
            geoEqualEarth()
                .fitExtent(
                    [
                        [12, 18],
                        [WIDTH - 12, HEIGHT - 18],
                    ],
                    { type: "Sphere" },
                ),
        [],
    );
    const path = useMemo(() => geoPath(projection), [projection]);
    const graticule = useMemo(() => geoGraticule().step([30, 30])(), []);

    const project = useMemo(() => (lng: number, lat: number) => {
        const point = projection([lng, lat]) ?? [WIDTH / 2, HEIGHT / 2];
        return { x: point[0], y: point[1] };
    }, [projection]);

    const targetPoint = useMemo(() => project(TARGET.lng, TARGET.lat), [project]);
    const mapData = useMemo<Source[]>(() => {
        const grouped = new Map<string, Source>();
        for (const log of threatLogs) {
            if (!log.country || log.country === "XX") {
                continue;
            }
            const meta = COUNTRY_COORDS[log.country];
            const hasCoordinates = typeof log.latitude === "number" && typeof log.longitude === "number";
            if (!meta && !hasCoordinates) {
                continue;
            }
            const countryMeta = meta ?? {
                name: log.countryName ?? log.country,
                lat: log.latitude as number,
                lng: log.longitude as number,
                color: "#38bdf8",
            };
            const current = grouped.get(log.country) ?? {
                ...countryMeta,
                count: 0,
                topIp: log.ip,
                dominantTtp: log.mitreId || log.type,
                topHassh: log.hassh || "unknown",
            };
            current.count += 1;
            if (hasCoordinates) {
                current.lat = log.latitude as number;
                current.lng = log.longitude as number;
            }
            if (!current.topIp || current.topIp === "0.0.0.0") {
                current.topIp = log.ip;
            }
            grouped.set(log.country, current);
        }
        return [...grouped.values()];
    }, [threatLogs]);
    const sources = useMemo(() => {
        return mapData.map((source) => {
            const start = project(source.lng, source.lat);
            const midX = (start.x + targetPoint.x) / 2;
            const midY = (start.y + targetPoint.y) / 2;
            const distance = Math.hypot(targetPoint.x - start.x, targetPoint.y - start.y);
            const path = `M ${start.x},${start.y} Q ${midX},${midY - distance * 0.18} ${targetPoint.x},${targetPoint.y}`;
            return { ...source, point: start, path };
        });
    }, [mapData, project, targetPoint]);

    const land = theme === "dark" ? "#171717" : "#dbeafe";
    const selectedLand = theme === "dark" ? "#1d4ed8" : "#93c5fd";
    const landStroke = theme === "dark" ? "#2f3747" : "#ffffff";
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
                ? "fixed inset-0 m-auto w-[95vw] h-[90vh] z-[100] origin-center bg-slate-50 dark:bg-[#050505] rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col justify-center animate-in zoom-in-95 fade-in duration-200"
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
                        <path
                            d={path(graticule) ?? undefined}
                            fill="none"
                            stroke={theme === "dark" ? "#1f2937" : "#cbd5e1"}
                            strokeWidth="0.45"
                            opacity="0.55"
                        />
                        <g stroke={landStroke} strokeWidth="0.65">
                            {countries.map((country) => {
                                const name = country.properties?.name ?? "";
                                const selected = selectedRegion === name || selectedRegion === "USA" && name === "United States of America";
                                return (
                                    <path
                                        key={name}
                                        d={path(country as never) ?? undefined}
                                        fill={selected ? selectedLand : land}
                                        opacity={selectedRegion && !selected ? 0.35 : 0.92}
                                    >
                                        <title>{name}</title>
                                    </path>
                                );
                            })}
                        </g>

                        {underAttack && sources.map((source, index) => {
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
                                    <text
                                        x={source.point.x + 8}
                                        y={source.point.y - 8}
                                        fill={theme === "dark" ? "#dbeafe" : "#1e3a8a"}
                                        fontSize="10"
                                        fontWeight="700"
                                        paintOrder="stroke"
                                        stroke={theme === "dark" ? "#050505" : "#f8fafc"}
                                        strokeWidth="3"
                                    >
                                        {source.name}
                                    </text>
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
                            <span className={`w-2 h-2 rounded-full ${underAttack ? "bg-red-500 animate-pulse" : "bg-emerald-500"}`}></span>
                            {underAttack ? "UNDER ATTACK" : "MONITORING"}
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
