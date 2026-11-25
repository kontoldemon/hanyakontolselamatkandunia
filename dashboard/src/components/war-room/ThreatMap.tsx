"use client";

import { useTheme } from "next-themes";
import { MouseEvent, useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import { geoEqualEarth, geoGraticule, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import { ThreatLog, useLiveThreatLogs } from "@/lib/liveEvents";
import { COUNTRY_COORDS, getCountryCode } from "./countryGeoData";

const TARGET = {
    name: "CloudSentinel HQ",
    lat: 4.5,
    lng: 101.6869,
};

const ACTIVE_ATTACK_WINDOW_MS = 45_000;

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
    badge?: string;
    subtitle?: string;
    accent?: "danger" | "warning" | "info" | "neutral";
    details?: TooltipDetails[];
    x: number;
    y: number;
};

const WIDTH = 800;
const HEIGHT = 400;
const CROSSHAIR_DARK = "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='21' height='21' viewBox='0 0 21 21' fill='none' stroke='%23ffffff' stroke-width='1.5'%3E%3Cline x1='10.5' y1='2' x2='10.5' y2='19'/%3E%3Cline x1='2' y1='10.5' x2='19' y2='10.5'/%3E%3C/svg%3E\") 10 10, crosshair";
const CROSSHAIR_LIGHT = "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='21' height='21' viewBox='0 0 21 21' fill='none' stroke='%23000000' stroke-width='1.5'%3E%3Cline x1='10.5' y1='2' x2='10.5' y2='19'/%3E%3Cline x1='2' y1='10.5' x2='19' y2='10.5'/%3E%3C/svg%3E\") 10 10, crosshair";

type CountryFeature = {
    type: "Feature";
    properties?: { name?: string };
};

type Source = {
    name: string;
    lat: number;
    lng: number;
    count: number;
    recentCount: number;
    latestEpochMs: number;
    latestType: string;
    color: string;
    topIp: string;
    dominantTtp: string;
    topHassh: string;
    countryCode: string;
};

function attackColorForType(type: string, fallback: string): string {
    if (type === "SSH_AUTH_FAIL") return "#f43f5e";
    if (type === "COMMAND_EXEC") return "#f59e0b";
    return fallback || "#38bdf8";
}

function tooltipForSource(source: Source, isActive: boolean, event: MouseEvent<SVGElement>): TooltipState {
    const hasshLabel = source.topHassh && source.topHassh.length > 4 ? source.topHassh.slice(0, 12) : "Scanning...";
    const velocityLabel = isActive
        ? `${Math.max(1, source.recentCount)} ATK/min`
        : "Idle";
    return {
        title: source.name,
        badge: source.countryCode,
        subtitle: isActive ? "Active Threat Vector" : "Recent Threat Origin (Idle)",
        accent: isActive ? (source.latestType === "COMMAND_EXEC" ? "warning" : "danger") : "neutral",
        details: [
            { label: "Top IP", value: source.topIp },
            { label: "Attacks", value: `${source.count.toLocaleString()} (${velocityLabel})` },
            { label: "Dom. TTP", value: source.dominantTtp },
            { label: "HASSH", value: hasshLabel },
        ],
        x: event.clientX,
        y: event.clientY,
    };
}

function tooltipForCountry(name: string, cc: string, source: Source | undefined, isActive: boolean, event: MouseEvent<SVGElement>): TooltipState {
    if (source) {
        return tooltipForSource(source, isActive, event);
    }
    return {
        title: name,
        badge: cc || undefined,
        subtitle: "No recorded activity",
        accent: "neutral",
        x: event.clientX,
        y: event.clientY,
    };
}

export default function ThreatMap({ onRegionClick, selectedRegion, underAttack = false, threatLogs: externalLogs }: ThreatMapProps = {}) {
    const { theme } = useTheme();
    const [isExpanded, setIsExpanded] = useState(false);
    const [tooltipContent, setTooltipContent] = useState<TooltipState | null>(null);
    const [countries, setCountries] = useState<CountryFeature[]>([]);
    const [nowMs, setNowMs] = useState<number>(() => Date.now());
    const mounted = useSyncExternalStore(
        () => () => {},
        () => true,
        () => false,
    );
    const liveLogs = useLiveThreatLogs(!externalLogs);
    const threatLogs = externalLogs ?? liveLogs;

    useEffect(() => {
        const timer = window.setInterval(() => setNowMs(Date.now()), 2000);
        return () => window.clearInterval(timer);
    }, []);

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
        () => {
            if (isExpanded) {
                // In fullscreen, fit world map cleanly with top/bottom margin so northern and southern countries are never cut off
                return geoEqualEarth()
                    .fitExtent(
                        [
                            [2, 8],
                            [WIDTH - 2, HEIGHT - 8],
                        ],
                        { type: "Sphere" },
                    );
            }
            return geoEqualEarth()
                .fitExtent(
                    [
                        [12, 18],
                        [WIDTH - 12, HEIGHT - 18],
                    ],
                    { type: "Sphere" },
                );
        },
        [isExpanded],
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
        const recentCutoff = nowMs - 60_000;
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
                countryCode: log.country,
                count: 0,
                recentCount: 0,
                latestEpochMs: 0,
                latestType: log.type,
                topIp: log.ip,
                dominantTtp: log.mitreId || log.type,
                topHassh: "",
            };
            current.count += 1;
            if (log.epochMs >= recentCutoff) {
                current.recentCount += 1;
            }
            if (log.epochMs >= current.latestEpochMs) {
                current.latestEpochMs = log.epochMs;
                current.latestType = log.type;
                current.dominantTtp = log.mitreId || log.type;
                current.color = attackColorForType(log.type, countryMeta.color);
                if (log.ip && log.ip !== "0.0.0.0") {
                    current.topIp = log.ip;
                }
            }
            if (log.hassh && log.hassh.length > 4 && (!current.topHassh || current.topHassh === "N/A" || current.topHassh === "unknown")) {
                current.topHassh = log.hassh;
            }
            if (!meta && hasCoordinates) {
                current.lat = log.latitude as number;
                current.lng = log.longitude as number;
            }
            grouped.set(log.country, current);
        }
        return [...grouped.values()];
    }, [threatLogs, nowMs]);

    const sources = useMemo(() => {
        return mapData.map((source) => {
            const start = project(source.lng, source.lat);
            const midX = (start.x + targetPoint.x) / 2;
            const midY = (start.y + targetPoint.y) / 2;
            const distance = Math.hypot(targetPoint.x - start.x, targetPoint.y - start.y);
            const arcPath = `M ${start.x},${start.y} Q ${midX},${midY - distance * 0.2} ${targetPoint.x},${targetPoint.y}`;
            const isActive = underAttack && (nowMs - source.latestEpochMs <= ACTIVE_ATTACK_WINDOW_MS);
            const velocityScore = Math.min(6, Math.max(1, source.recentCount || Math.ceil(source.count / 3)));
            const durationSec = Number(Math.max(0.85, 2.7 - velocityScore * 0.3).toFixed(2));
            return { ...source, point: start, path: arcPath, isActive, durationSec };
        });
    }, [mapData, project, targetPoint, underAttack, nowMs]);

    const sourceByCC = useMemo(() => {
        const map = new Map<string, (typeof sources)[number]>();
        for (const s of sources) {
            map.set(s.countryCode, s);
        }
        return map;
    }, [sources]);

    const hasAnyActiveArc = useMemo(() => sources.some((s) => s.isActive), [sources]);

    const selectedCC = useMemo(() => {
        if (!selectedRegion) return null;
        const matchedSource = sources.find((s) => s.topIp === selectedRegion);
        if (matchedSource) return matchedSource.countryCode;
        if (selectedRegion.length === 2) return selectedRegion.toUpperCase();
        return getCountryCode(selectedRegion);
    }, [selectedRegion, sources]);

    const land = theme === "dark" ? "#171920" : "#dbeafe";
    const selectedLand = theme === "dark" ? "#2563eb" : "#3b82f6";
    const landStroke = theme === "dark" ? "#2a3140" : "#ffffff";
    const ocean = theme === "dark" ? "#050505" : "#f8fafc";

    const selectSource = useCallback((topIp: string) => {
        onRegionClick?.(selectedRegion === topIp ? null : topIp);
    }, [onRegionClick, selectedRegion]);

    useEffect(() => {
        const handleFocusThreatMap = () => {
            setIsExpanded(true);
        };
        window.addEventListener("agent:focus-threat-map", handleFocusThreatMap);
        return () => window.removeEventListener("agent:focus-threat-map", handleFocusThreatMap);
    }, []);

    const renderSources = useMemo(() => {
        return sources.map((source, index) => {
            const isDimmed = selectedRegion && selectedRegion !== source.name && selectedRegion !== source.topIp && selectedCC !== source.countryCode;
            const isLeftOfTarget = source.point.x < targetPoint.x;
            const delaySec = ((index * 0.27) % 1.2).toFixed(2);
            return (
                <g key={source.countryCode} opacity={isDimmed ? 0.2 : 1}>
                    {/* Subtle trajectory guide */}
                    <path
                        d={source.path}
                        fill="none"
                        stroke={source.color}
                        strokeWidth={source.isActive ? "1.4" : "0.9"}
                        strokeOpacity={theme === "dark" ? (source.isActive ? 0.28 : 0.1) : (source.isActive ? 0.55 : 0.25)}
                        strokeLinecap="round"
                    />

                    {/* FortiGuard-style animated laser/comet beam when actively attacking */}
                    {source.isActive && (
                        <>
                            <path
                                d={source.path}
                                fill="none"
                                stroke={theme === "dark" ? source.color : (source.color === "#38bdf8" ? "#0284c7" : source.color)}
                                strokeWidth={theme === "dark" ? "2.2" : "2.5"}
                                strokeLinecap="round"
                                pathLength={100}
                                strokeDasharray="22 118"
                                filter="url(#attack-glow)"
                                style={{
                                    animation: `attackBeamFlow ${source.durationSec}s cubic-bezier(0.25, 0.1, 0.25, 1) ${delaySec}s infinite`,
                                }}
                            />
                            <circle r={theme === "dark" ? "2.6" : "3"} fill={theme === "dark" ? "#ffffff" : source.color} filter="url(#attack-glow)">
                                <animateMotion
                                    dur={`${source.durationSec}s`}
                                    begin={`${delaySec}s`}
                                    repeatCount="indefinite"
                                    path={source.path}
                                />
                            </circle>
                        </>
                    )}

                    <text
                        x={source.point.x + (isLeftOfTarget ? -9 : 9)}
                        y={source.point.y + 3}
                        textAnchor={isLeftOfTarget ? "end" : "start"}
                        fill={theme === "dark" ? "#dbeafe" : "#1e3a8a"}
                        fontSize="9.5"
                        fontWeight="600"
                        paintOrder="stroke"
                        stroke={theme === "dark" ? "#050505" : "#f8fafc"}
                        strokeWidth="3.5"
                        className="pointer-events-none select-none"
                    >
                        {source.name}
                    </text>

                    <g
                        role="button"
                        tabIndex={0}
                        onClick={() => selectSource(source.topIp)}
                        onMouseEnter={(event) => setTooltipContent(tooltipForSource(source, source.isActive, event))}
                        onMouseMove={(event) => setTooltipContent((previous) => previous ? { ...previous, x: event.clientX, y: event.clientY } : null)}
                        onMouseLeave={() => setTooltipContent(null)}
                        className="cursor-pointer outline-none focus:outline-none"
                    >
                        <circle cx={source.point.x} cy={source.point.y} r="14" fill="transparent" />
                        <circle
                            cx={source.point.x}
                            cy={source.point.y}
                            r={source.isActive ? "8" : "5.5"}
                            fill={source.color}
                            opacity={source.isActive ? "0.24" : "0.14"}
                        />
                        {source.isActive && (
                            <circle
                                cx={source.point.x}
                                cy={source.point.y}
                                r="4.5"
                                fill={source.color}
                                className="animate-pulse"
                            />
                        )}
                        <circle cx={source.point.x} cy={source.point.y} r="2.8" fill={source.color} />
                    </g>
                </g>
            );
        });
    }, [sources, selectedRegion, selectedCC, theme, selectSource, targetPoint]);

    const clampedTooltipStyle = useMemo(() => {
        if (!tooltipContent) return undefined;
        const pad = 16;
        const winW = typeof window !== "undefined" ? window.innerWidth : 1280;
        const winH = typeof window !== "undefined" ? window.innerHeight : 800;
        const left = Math.min(Math.max(tooltipContent.x, 140 + pad), winW - 140 - pad);
        const isNearTop = tooltipContent.y < 230;
        const top = isNearTop
            ? Math.min(Math.max(tooltipContent.y, pad), winH - 240)
            : Math.min(Math.max(tooltipContent.y, 220), winH - pad);
        return { left, top, isNearTop };
    }, [tooltipContent]);

    return (
        <>
            {isExpanded && (
                <div className="fixed inset-0 z-[199] bg-black/80 backdrop-blur-sm animate-in fade-in duration-200" onClick={() => setIsExpanded(false)} />
            )}
            <div className={isExpanded
                ? "fixed inset-1 md:inset-3 z-[200] origin-center bg-slate-50 dark:bg-[#050505] rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col justify-center animate-in zoom-in-95 fade-in duration-200"
                : "relative w-full h-full flex flex-col bg-slate-50 dark:bg-[#050505] overflow-hidden group"}>
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className={`absolute top-3 right-3 z-[80] bg-black/60 hover:bg-black p-1.5 rounded-lg text-white backdrop-blur border border-white/10 transition-all ${isExpanded ? "opacity-100 scale-100" : "opacity-0 scale-90 group-hover:opacity-100 group-hover:scale-100"}`}
                    title={isExpanded ? "Collapse Map" : "Expand Map"}
                >
                    {isExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                </button>

                <style>{`
                    .threat-map-canvas, .threat-map-canvas * {
                        cursor: ${theme === "dark" ? CROSSHAIR_DARK : CROSSHAIR_LIGHT} !important;
                    }
                    html.dark .threat-map-canvas, html.dark .threat-map-canvas * {
                        cursor: ${CROSSHAIR_DARK} !important;
                    }
                    html:not(.dark) .threat-map-canvas, html:not(.dark) .threat-map-canvas * {
                        cursor: ${CROSSHAIR_LIGHT} !important;
                    }
                `}</style>

                <div className={`relative flex-1 w-full flex overflow-hidden threat-map-canvas ${isExpanded ? "items-center justify-center p-1 md:p-2" : ""}`}>
                    <div
                        className="absolute inset-0 opacity-20 pointer-events-none"
                        style={{
                            backgroundImage: `radial-gradient(${theme === "dark" ? "#333" : "#ccc"} 1px, transparent 1px)`,
                            backgroundSize: "20px 20px",
                        }}
                    />

                    <svg
                        className="threat-map-svg relative z-10 w-full h-full outline-none focus:outline-none select-none"
                        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
                        role="img"
                        aria-label="CloudSentinel global threat map"
                    >
                        <defs>
                            <filter id="attack-glow" x="-40%" y="-40%" width="180%" height="180%">
                                <feGaussianBlur stdDeviation="2.2" result="blur" />
                                <feMerge>
                                    <feMergeNode in="blur" />
                                    <feMergeNode in="SourceGraphic" />
                                </feMerge>
                            </filter>
                        </defs>

                        <rect width={WIDTH} height={HEIGHT} fill={ocean} />
                        <path
                            d={path(graticule) ?? undefined}
                            fill="none"
                            stroke={theme === "dark" ? "#1f2937" : "#cbd5e1"}
                            strokeWidth="0.45"
                            opacity="0.5"
                        />
                        <g stroke={landStroke} strokeWidth="0.65">
                            {countries.map((country) => {
                                const name = country.properties?.name ?? "";
                                const cc = getCountryCode(name);
                                const selected = !!selectedCC && selectedCC === cc;
                                const matchedSource = cc ? sourceByCC.get(cc) : undefined;
                                return (
                                    <path
                                        key={name}
                                        d={path(country as never) ?? undefined}
                                        fill={selected ? selectedLand : land}
                                        opacity={selectedRegion && !selected ? 0.35 : 0.92}
                                        onClick={() => {
                                            if (!cc) return;
                                            const val = matchedSource?.topIp || cc;
                                            onRegionClick?.(selectedRegion === val ? null : val);
                                        }}
                                        onMouseEnter={(event) =>
                                            setTooltipContent(
                                                tooltipForCountry(name, cc, matchedSource, !!matchedSource?.isActive, event),
                                            )
                                        }
                                        onMouseMove={(event) =>
                                            setTooltipContent((previous) =>
                                                previous ? { ...previous, x: event.clientX, y: event.clientY } : null,
                                            )
                                        }
                                        onMouseLeave={() => setTooltipContent(null)}
                                        className={`cursor-pointer outline-none focus:outline-none transition-colors duration-200 ${!selected ? "hover:fill-blue-500/20 dark:hover:fill-blue-400/20" : ""}`}
                                    />
                                );
                            })}
                        </g>

                        {renderSources}

                        {/* Target Honeypot Node */}
                        <g
                            onMouseEnter={(event) =>
                                setTooltipContent({
                                    title: TARGET.name,
                                    badge: "MY",
                                    subtitle: hasAnyActiveArc ? "Receiving Live Attack Traffic" : "Local Honeypot Sensor",
                                    accent: hasAnyActiveArc ? "danger" : "info",
                                    x: event.clientX,
                                    y: event.clientY,
                                })
                            }
                            onMouseMove={(event) => setTooltipContent((previous) => previous ? { ...previous, x: event.clientX, y: event.clientY } : null)}
                            onMouseLeave={() => setTooltipContent(null)}
                            className="cursor-pointer outline-none focus:outline-none"
                        >
                            {hasAnyActiveArc && (
                                <circle
                                    cx={targetPoint.x}
                                    cy={targetPoint.y}
                                    r="9"
                                    fill="none"
                                    stroke="#ef4444"
                                    strokeWidth="1.5"
                                    style={{
                                        transformOrigin: `${targetPoint.x}px ${targetPoint.y}px`,
                                        animation: "targetImpactRipple 1.6s cubic-bezier(0, 0.2, 0.8, 1) infinite",
                                    }}
                                />
                            )}
                            <circle cx={targetPoint.x} cy={targetPoint.y} r="9" fill="rgba(16, 185, 129, 0.22)" stroke="#10b981" strokeWidth="1.2" />
                            <circle cx={targetPoint.x} cy={targetPoint.y} r="3.5" fill="#10b981" className="animate-pulse" />
                        </g>
                    </svg>

                    {/* Minimalist Compact Global DEFCON Pill */}
                    {(() => {
                        const isAttackActive = mounted && underAttack;
                        return (
                            <div
                                suppressHydrationWarning
                                className={`absolute left-3 z-[60] pointer-events-none inline-flex items-center gap-2 rounded-full border border-slate-200/80 dark:border-white/10 bg-white/80 dark:bg-black/65 px-2.5 py-1 backdrop-blur-md shadow-sm ${isExpanded ? "top-4 left-4" : "top-3"}`}
                            >
                                <span className="relative flex h-1.5 w-1.5" suppressHydrationWarning>
                                    {isAttackActive && (
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-500 opacity-75" />
                                    )}
                                    <span className={`relative inline-flex rounded-full h-1.5 w-1.5 ${isAttackActive ? "bg-rose-500" : "bg-emerald-500"}`} />
                                </span>
                                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">
                                    DEFCON
                                </span>
                                <span suppressHydrationWarning className={`text-[10.5px] font-mono font-bold tracking-wider ${isAttackActive ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                                    {isAttackActive ? "UNDER ATTACK" : "MONITORING"}
                                </span>
                            </div>
                        );
                    })()}

                    {/* Custom Glassmorphic Country & Node Tooltip */}
                    {tooltipContent && clampedTooltipStyle && (
                        <div
                            className={`fixed z-[120] pointer-events-none -translate-x-1/2 ${clampedTooltipStyle.isNearTop ? "mt-3" : "-translate-y-full -mt-3"} min-w-[195px] max-w-[275px] rounded-2xl border border-slate-900/15 dark:border-white/20 bg-slate-900/[0.06] dark:bg-black/[0.30] px-3.5 py-2.5 text-slate-900 dark:text-slate-100 shadow-[0_16px_36px_rgba(0,0,0,0.35),0_4px_12px_rgba(0,0,0,0.1),inset_0_1px_1px_rgba(255,255,255,0.15)] transition-all duration-150 overflow-hidden`}
                            style={{
                                ...clampedTooltipStyle,
                                backdropFilter: "blur(1.5px)",
                                WebkitBackdropFilter: "blur(1.5px)",
                            }}
                        >
                            {/* Subtle light specular shine on top rim */}
                            <div className="absolute top-0 left-0 right-0 h-10 bg-gradient-to-b from-white/12 dark:from-white/8 to-transparent pointer-events-none rounded-t-2xl" />

                            <div className="relative flex items-center justify-between gap-2">
                                <span className="font-display text-xs font-bold tracking-tight text-slate-900 dark:text-white truncate">
                                    {tooltipContent.title}
                                </span>
                                {tooltipContent.badge && (
                                    <span className="shrink-0 rounded-md bg-white/40 dark:bg-white/10 px-1.5 py-0.5 font-mono text-[9px] font-semibold text-slate-700 dark:text-slate-200 border border-slate-300/60 dark:border-white/15 backdrop-blur-md">
                                        {tooltipContent.badge}
                                    </span>
                                )}
                            </div>
                            {tooltipContent.subtitle && (
                                <div
                                    className={`relative mt-0.5 text-[10px] font-medium ${
                                        tooltipContent.accent === "danger"
                                            ? "text-rose-600 dark:text-rose-400"
                                            : tooltipContent.accent === "warning"
                                                ? "text-amber-600 dark:text-amber-400"
                                                : tooltipContent.accent === "info"
                                                    ? "text-blue-600 dark:text-blue-400"
                                                    : "text-slate-500 dark:text-slate-400"
                                    }`}
                                >
                                    {tooltipContent.subtitle}
                                </div>
                            )}

                            {tooltipContent.details && tooltipContent.details.length > 0 && (
                                <div className="relative mt-2 flex flex-col gap-1 border-t border-slate-300/40 dark:border-white/10 pt-1.5">
                                    {tooltipContent.details.map((detail, idx) => (
                                        <div key={idx} className="flex items-center justify-between gap-3 text-[10.5px]">
                                            <span className="text-slate-500 dark:text-slate-400 font-medium">{detail.label}</span>
                                            <span className="font-mono font-semibold text-blue-600 dark:text-blue-300 truncate max-w-[135px]">
                                                {detail.value}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
                {!isExpanded && (
                    <div className="relative border-t border-slate-200 dark:border-white/10 bg-white dark:bg-[#050505] overflow-hidden text-[11px] shrink-0 z-[40] w-full flex items-center h-9">
                        <div className="absolute left-0 top-0 bottom-0 z-10 flex items-center pl-3 pr-8 bg-gradient-to-r from-white via-white to-transparent dark:from-[#050505] dark:via-[#050505] dark:to-transparent">
                            <span className="font-display text-[10.5px] font-semibold text-slate-800 dark:text-slate-200 uppercase tracking-wider shrink-0 flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                                Intel Feed
                            </span>
                        </div>
                        <div className="flex items-center gap-4 whitespace-nowrap opacity-80 animate-[marquee_40s_linear_infinite] hover:[animation-play-state:paused] pl-[125px]">
                            {threatLogs.length === 0 && <span className="text-slate-500 text-[11px]">Awaiting initial sensor data stream...</span>}
                            {Array.from(new Map(threatLogs.map((log) => [log.ip, log])).values()).slice(0, 10).map((log, i) => (
                                <span key={i} className="flex items-center gap-2 text-[11px] text-slate-600 dark:text-slate-400">
                                    <span className="font-mono text-blue-600 dark:text-blue-400">{log.ip}</span>
                                    <span>attempted</span>
                                    <span className="font-mono text-rose-500">{log.type}</span>
                                    <span>&bull;</span>
                                </span>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </>
    );
}
