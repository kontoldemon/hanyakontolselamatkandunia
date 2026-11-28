"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useListRef } from "react-window";
import { useCapturedSessions, useLiveThreatLogs, type CapturedSession } from "@/lib/liveEvents";
import { useAgentCommand } from "@/lib/AgentContext";
import type { SessionRowData } from "@/components/sessions/SessionListRow";

const sessionLastSeenMs = (session: CapturedSession) =>
    session.lastSeenEpochMs ??
    session.firstSeenEpochMs ??
    session.startedAtEpochMs ??
    0;

const sessionCreatedMs = (session: CapturedSession) =>
    session.startedAtEpochMs ??
    session.firstSeenEpochMs ??
    session.lastSeenEpochMs ??
    0;

export type SessionFilterStatus = "all" | "active" | "most_attacks" | "least_attacks" | "high_risk";

export function useSessionsViewController() {
    const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
    const [lastSelectedIp, setLastSelectedIp] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [filterStatus, setFilterStatus] = useState<SessionFilterStatus>("all");
    const [blockingIp, setBlockingIp] = useState<string | null>(null);
    const [confirmBlockIp, setConfirmBlockIp] = useState<string | null>(null);
    const [replayMode, setReplayMode] = useState<"attacker" | "both">("both");
    const [nowMs, setNowMs] = useState(() => Date.now());
    const sessions = useCapturedSessions();
    const liveLogs = useLiveThreatLogs();
    const [focusIp, setFocusIp] = useState("");
    const listRef = useListRef(null);
    const listContainerRef = useRef<HTMLDivElement | null>(null);
    const [listHeight, setListHeight] = useState(500);
    const [displayedSessions, setDisplayedSessions] = useState<CapturedSession[]>([]);
    const [currentPage, setCurrentPage] = useState(1);
    const PAGE_SIZE = 15;
    const lastNonEmptySessionsAtRef = useRef(0);
    const lastSelectedSnapshotRef = useRef<CapturedSession | null>(null);
    const replayCacheRef = useRef<Map<string, NonNullable<CapturedSession["replay"]>>>(new Map());
    const inputCacheRef = useRef<Map<string, NonNullable<CapturedSession["input"]>>>(new Map());

    const filteredSessions = useMemo(() => {
        const byIp = new Map<string, CapturedSession[]>();
        const query = searchQuery.toLowerCase();

        const hasReplay = (session: CapturedSession) =>
            (session.replay?.length ?? 0) > 0 || (session.input?.length ?? 0) > 0;

        for (const session of sessions) {
            const matches = session.ip.toLowerCase().includes(query) ||
                session.country.toLowerCase().includes(query) ||
                (session.countryName && session.countryName.toLowerCase().includes(query)) ||
                (session.fingerprint && session.fingerprint.toLowerCase().includes(query)) ||
                (session.client && session.client.toLowerCase().includes(query));
            if (!matches) {
                continue;
            }
            const bucket = byIp.get(session.ip);
            if (bucket) {
                bucket.push(session);
            } else {
                byIp.set(session.ip, [session]);
            }
        }

        const selected: CapturedSession[] = [];
        for (const ipSessions of byIp.values()) {
            const sorted = [...ipSessions].sort((a, b) => sessionLastSeenMs(b) - sessionLastSeenMs(a));
            const newest = sorted[0];
            const newestActive = sorted.find((session) => (session.status || "").toLowerCase() === "active");
            const base = filterStatus === "active" ? newestActive : newest;

            if (!base) {
                continue;
            }
            const allReplay = sorted
                .slice()
                .reverse()
                .flatMap((session) => session.replay ?? []);
            const replaySeen = new Set<string>();
            const mergedReplay = allReplay
                .filter((entry) => {
                    const text = (entry.text || "").trim().toLowerCase();
                    if (!text || text.startsWith("cloudsentinel.") || text.includes("[redacted]")) {
                        return false;
                    }
                    const key = `${entry.role}|${entry.timestamp ?? ""}|${entry.text}`;
                    if (replaySeen.has(key)) {
                        return false;
                    }
                    replaySeen.add(key);
                    return true;
                });

            const mergedInput = Array.from(
                new Set(
                    sorted
                        .slice()
                        .reverse()
                        .flatMap((session) => session.input ?? [])
                        .map((value) => value.trim())
                        .filter(Boolean),
                ),
            );

            const replaySource = sorted.find(hasReplay);
            selected.push({
                ...base,
                input: mergedInput.length > 0 ? mergedInput : (base.input ?? []),
                replay: mergedReplay.length > 0 ? mergedReplay : (base.replay ?? []),
                mitreTechniques: Array.from(
                    new Set(sorted.flatMap((session) => session.mitreTechniques ?? [])),
                ),
                fingerprint: base.fingerprint || replaySource?.fingerprint || "",
                client: (base.client && base.client !== "unknown")
                    ? base.client
                    : (replaySource?.client ?? base.client ?? "unknown"),
            });
        }

        let result = selected;
        if (filterStatus === "high_risk") {
            result = result.filter((s) => (s.riskScore ?? 0) >= 80);
        }

        if (filterStatus === "most_attacks") {
            return result.sort((a, b) => (b.input?.length ?? 0) - (a.input?.length ?? 0));
        }
        if (filterStatus === "least_attacks") {
            return result.sort((a, b) => (a.input?.length ?? 0) - (b.input?.length ?? 0));
        }

        return result.sort((a, b) => {
            const timeDiff = sessionCreatedMs(b) - sessionCreatedMs(a);
            if (timeDiff !== 0) return timeDiff;
            return a.ip.localeCompare(b.ip);
        });
    }, [sessions, searchQuery, filterStatus]);

    useEffect(() => {
        if (filteredSessions.length > 0) {
            setDisplayedSessions(filteredSessions);
            lastNonEmptySessionsAtRef.current = Date.now();
            return;
        }
        const staleFor = Date.now() - lastNonEmptySessionsAtRef.current;
        if (staleFor > 4000) {
            setDisplayedSessions([]);
        }
    }, [filteredSessions]);

    const totalPages = Math.max(1, Math.ceil(displayedSessions.length / PAGE_SIZE));

    useEffect(() => {
        setCurrentPage(1);
    }, [searchQuery, filterStatus]);

    useEffect(() => {
        if (currentPage > totalPages) {
            setCurrentPage(totalPages);
        }
    }, [currentPage, totalPages]);

    const pagedSessions = useMemo(() => {
        const start = (currentPage - 1) * PAGE_SIZE;
        return displayedSessions.slice(start, start + PAGE_SIZE);
    }, [displayedSessions, currentPage]);

    const selectSession = useCallback((session: CapturedSession) => {
        setSelectedSessionId(session.id);
        setLastSelectedIp(session.ip);
        lastSelectedSnapshotRef.current = session;
    }, []);

    useAgentCommand("sessions.search", useCallback((v: string) => setSearchQuery(v), []));
    useAgentCommand("sessions.filter", useCallback((v: string) => setFilterStatus(v as SessionFilterStatus), []));
    useAgentCommand("sessions.select", useCallback((ip: string) => {
        const index = displayedSessions.findIndex((s) => s.ip === ip);
        if (index >= 0) {
            const targetPage = Math.floor(index / PAGE_SIZE) + 1;
            setCurrentPage(targetPage);
            selectSession(displayedSessions[index]);
            const pageRowIndex = index % PAGE_SIZE;
            listRef.current?.scrollToRow({ index: pageRowIndex, align: "center", behavior: "smooth" });
        }
    }, [displayedSessions, selectSession, listRef]));

    const exactMatchDisplayed = selectedSessionId ? displayedSessions.find((s) => s.id === selectedSessionId) : null;
    const exactMatchRaw = selectedSessionId ? sessions.find((s) => s.id === selectedSessionId) : null;
    const selectedByIpDisplayed = lastSelectedIp
        ? displayedSessions
            .filter((s) => s.ip === lastSelectedIp)
            .sort((a, b) => sessionLastSeenMs(b) - sessionLastSeenMs(a))[0] ?? null
        : null;
    const selectedByIpRaw = lastSelectedIp
        ? sessions
            .filter((s) => s.ip === lastSelectedIp)
            .sort((a, b) => sessionLastSeenMs(b) - sessionLastSeenMs(a))[0] ?? null
        : null;
    const selectedSession =
        exactMatchDisplayed ||
        selectedByIpDisplayed ||
        exactMatchRaw ||
        selectedByIpRaw ||
        lastSelectedSnapshotRef.current;

    const selectedSessionLive = useMemo(() => {
        if (!selectedSession) {
            return selectedSession;
        }
        const baseLastSeen = selectedSession.lastSeenEpochMs ?? 0;
        const merged: CapturedSession = {
            ...selectedSession,
            input: [...(selectedSession.input ?? [])],
            replay: [...(selectedSession.replay ?? [])],
        };
        const seenReplay = new Set(
            (merged.replay ?? []).map((entry) => `${entry.role}|${entry.timestamp ?? ""}|${entry.text}`),
        );
        let liveLastSeen = baseLastSeen;

        for (const log of liveLogs) {
            if (log.ip !== selectedSession.ip || log.epochMs <= baseLastSeen) {
                continue;
            }
            liveLastSeen = Math.max(liveLastSeen, log.epochMs);
            const rawText = (log.payload ?? "").trim();
            if (!rawText || rawText.includes("[redacted]")) {
                continue;
            }
            const lower = rawText.toLowerCase();
            const infoText =
                lower.startsWith("cloudsentinel.session.connect")
                    ? "[OPEN] Session opened"
                    : lower.startsWith("cloudsentinel.session.closed")
                        ? "[CLOSE] Session closed"
                        : lower.startsWith("cloudsentinel.client.version")
                            ? "[VERSION] Client banner observed"
                            : lower === "auth-attempt" || lower.startsWith("cloudsentinel.login.failed") || lower.startsWith("cloudsentinel.login.success")
                                ? "[AUTH] Authentication event"
                                : null;
            const text = infoText ?? rawText;
            const role = infoText ? "honeypot" : (log.role ?? (log.type === "HONEYPOT_RESPONSE" ? "honeypot" : "attacker"));
            const replayKey = `${role}|${log.timestamp ?? ""}|${text}`;
            if (!seenReplay.has(replayKey)) {
                seenReplay.add(replayKey);
                merged.replay?.push({ role, text, timestamp: log.timestamp });
            }
            if (role === "attacker") {
                merged.input?.push(text);
            }
        }

        if (liveLastSeen > baseLastSeen) {
            merged.lastSeenEpochMs = liveLastSeen;
            merged.status = "Active";
        }
        merged.replay = merged.replay ?? [];
        merged.input = Array.from(new Set((merged.input ?? []).filter(Boolean)));
        return merged;
    }, [selectedSession, liveLogs]);

    useEffect(() => {
        if (selectedSession) {
            lastSelectedSnapshotRef.current = selectedSession;
        }
    }, [selectedSession]);

    useEffect(() => {
        const exactMatch = exactMatchDisplayed || exactMatchRaw;
        if (!exactMatch && selectedSession && selectedSessionId !== selectedSession.id) {
            setSelectedSessionId(selectedSession.id);
        }
    }, [exactMatchDisplayed, exactMatchRaw, selectedSession, selectedSessionId]);

    const selectedView = useMemo(() => {
        const base = selectedSessionLive ?? selectedSession;
        if (!base) return base;
        const key = base.id;
        const cachedReplay = replayCacheRef.current.get(key) ?? [];
        const cachedInput = inputCacheRef.current.get(key) ?? [];
        const seenReplay = new Set<string>();
        const replay = [...cachedReplay, ...(base.replay ?? [])].filter((entry) => {
            const entryKey = `${entry.role}|${entry.timestamp ?? ""}|${entry.text}`;
            if (seenReplay.has(entryKey)) {
                return false;
            }
            seenReplay.add(entryKey);
            return true;
        });
        const input = Array.from(new Set([...cachedInput, ...(base.input ?? [])].filter(Boolean)));
        replayCacheRef.current.set(key, replay);
        inputCacheRef.current.set(key, input);
        return { ...base, replay, input };
    }, [selectedSessionLive, selectedSession]);

    useEffect(() => {
        setReplayMode("both");
        replayCacheRef.current.clear();
        inputCacheRef.current.clear();
    }, [selectedSessionId]);

    useEffect(() => {
        const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
        return () => window.clearInterval(timer);
    }, []);

    useEffect(() => {
        const el = listContainerRef.current;
        if (!el) {
            return;
        }
        const update = () => setListHeight(Math.max(220, el.clientHeight));
        update();
        const observer = new ResizeObserver(update);
        observer.observe(el);
        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }
        const params = new URLSearchParams(window.location.search);
        const value = params.get("focusIp")?.trim() ?? "";
        setFocusIp(value);
    }, []);

    useEffect(() => {
        if (!focusIp) {
            return;
        }
        setSearchQuery(focusIp);
    }, [focusIp]);

    const hasScrolledFocusRef = useRef(false);

    useEffect(() => {
        if (!focusIp || displayedSessions.length === 0 || hasScrolledFocusRef.current) {
            return;
        }
        const index = displayedSessions.findIndex((session) => session.ip === focusIp);
        if (index >= 0) {
            hasScrolledFocusRef.current = true;
            const targetPage = Math.floor(index / PAGE_SIZE) + 1;
            setCurrentPage(targetPage);
            selectSession(displayedSessions[index]);
            const pageRowIndex = index % PAGE_SIZE;
            listRef.current?.scrollToRow({ index: pageRowIndex, align: "center", behavior: "smooth" });
            setFocusIp("");
            if (typeof window !== "undefined" && window.location.search.includes("focusIp")) {
                const url = new URL(window.location.href);
                url.searchParams.delete("focusIp");
                window.history.replaceState({}, "", url.pathname + (url.search ? `?${url.searchParams.toString()}` : ""));
            }
        }
    }, [focusIp, displayedSessions, selectSession, listRef]);

    async function executeBlockIp(ip: string) {
        setBlockingIp(ip);
        try {
            const response = await fetch("/api/cloudsentinel/block-ip", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ip, ttl: 3600, reason: "manual-dashboard" }),
            });
            const data = await response.json();
            if (!data.ok) {
                window.alert(data.error ?? "Block failed");
            }
        } catch {
            window.alert("Block request failed");
        } finally {
            setBlockingIp(null);
            setConfirmBlockIp(null);
        }
    }

    const rowData: SessionRowData = {
        sessions: pagedSessions,
        selectedSessionId,
        focusIp,
        nowMs,
        searchQuery,
        onSelect: selectSession,
    };

    const clearSelection = useCallback(() => {
        setSelectedSessionId(null);
        setLastSelectedIp(null);
    }, []);

    return {
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
    };
}
