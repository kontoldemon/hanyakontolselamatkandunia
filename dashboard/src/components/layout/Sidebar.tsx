"use client";

import { useState, useCallback, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { LayoutDashboard, Terminal, BrainCircuit, Settings, LogOut, ChevronLeft, PanelLeftOpen, Moon, Sun } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { clsx } from "clsx";
import { useTheme } from "next-themes";
import { useSensorOperations, useWarRoomState } from "@/lib/liveEvents";
import { useAgentCommand } from "@/lib/AgentContext";

const SIDEBAR_COLLAPSED_KEY = "cloudsentinel.sidebar.collapsed";

export default function Sidebar() {
    const [isCollapsed, setIsCollapsed] = useState(() => {
        if (typeof window === "undefined") return false;
        return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
    });
    const [showSignOutConfirm, setShowSignOutConfirm] = useState(false);
    const pathname = usePathname();
    const router = useRouter();
    const { theme, setTheme } = useTheme();
    const operations = useSensorOperations();
    const warRoom = useWarRoomState();
    const exposurePaused = warRoom.exposure?.effectiveEnabled === false;
    const exposureSyncing = warRoom.exposure?.syncing === true;
    const statusPending = !exposurePaused && warRoom.updatedAt <= 0 && warRoom.ok === false;
    const sensorLive =
        (statusPending || !exposurePaused) &&
        (
            warRoom.state === "live" ||
            warRoom.state === "under_attack" ||
            statusPending ||
            operations?.source === "live" ||
            operations?.sensor.readiness.ok === true
        );

    useAgentCommand("sidebar.toggle", useCallback((v: string) => {
        if (v === "collapse") setIsCollapsed(true);
        else if (v === "expand") setIsCollapsed(false);
        else setIsCollapsed((p) => !p);
    }, []));
    useAgentCommand("sidebar.theme", useCallback((v: string) => {
        if (v === "dark" || v === "light") setTheme(v);
        else setTheme(theme === "dark" ? "light" : "dark");
    }, [theme, setTheme]));

    useEffect(() => {
        if (typeof window === "undefined") return;
        window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, isCollapsed ? "1" : "0");
    }, [isCollapsed]);

    const links = [
        { name: "War Room", href: "/dashboard", icon: LayoutDashboard },
        { name: "Sessions", href: "/sessions", icon: Terminal },
        { name: "Intelligence", href: "/intelligence", icon: BrainCircuit },
        { name: "Settings", href: "/settings", icon: Settings },
    ];

    async function signOut() {
        await fetch("/api/auth/logout", { method: "POST" });
        router.replace("/signin");
        router.refresh();
    }

    return (
        <>
            <aside
                className={clsx(
                    "hidden md:flex flex-col bg-white/50 dark:bg-[#050505] border-r border-slate-200 dark:border-white/10 transition-[width] duration-200 ease-in-out backdrop-blur-md h-screen sticky top-0",
                    isCollapsed ? "w-20" : "w-56"
                )}
            >
                <div className="h-14 px-3.5 border-b border-slate-200 dark:border-white/10 flex items-center justify-between">
                    <div className={clsx("flex items-center gap-2 overflow-hidden transition-all", isCollapsed ? "w-0 opacity-0" : "w-auto opacity-100")}>
                        <Link href="/dashboard" className="group flex items-center gap-2 text-left focus-visible:outline-none">
                            <Image
                                src="/logo.svg"
                                alt="CloudSentinel"
                                width={16}
                                height={16}
                                className="h-4 w-4 shrink-0 transition-transform duration-200 group-hover:scale-105"
                            />
                            <span className="font-display text-sm font-bold tracking-tight text-slate-900 dark:text-white whitespace-nowrap">
                                Cloud<span className="text-blue-600 dark:text-blue-400">Sentinel</span>
                            </span>
                        </Link>
                    </div>

                    <button
                        onClick={() => setIsCollapsed(!isCollapsed)}
                        className="group/expand relative flex h-8 w-8 items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 text-slate-500 dark:text-slate-400 transition-colors mx-auto"
                        title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
                        aria-label={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
                    >
                        {isCollapsed ? (
                            <>
                                <Image
                                    src="/logo.svg"
                                    alt="CloudSentinel"
                                    width={18}
                                    height={18}
                                    className="h-4.5 w-4.5 transition-all duration-200 group-hover/expand:opacity-0 group-hover/expand:scale-75"
                                />
                                <PanelLeftOpen
                                    size={18}
                                    className="absolute text-blue-600 dark:text-blue-400 opacity-0 scale-75 transition-all duration-200 group-hover/expand:opacity-100 group-hover/expand:scale-100"
                                />
                            </>
                        ) : (
                            <ChevronLeft size={16} />
                        )}
                    </button>
                </div>

                <nav className="flex-1 p-2.5 space-y-1.5 overflow-y-auto overflow-x-hidden">
                    {links.map((link) => {
                        const Icon = link.icon;
                        const isActive = pathname === link.href;

                        return (
                            <Link
                                key={link.href}
                                href={link.href}
                                title={isCollapsed ? link.name : ""}
                                className={clsx(
                                    "flex items-center px-2.5 py-2 rounded-lg transition-all text-xs font-medium whitespace-nowrap",
                                    isActive
                                        ? "bg-blue-50 text-blue-600 dark:bg-white/5 dark:text-blue-400 font-semibold"
                                        : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-slate-200",
                                    isCollapsed ? "justify-center py-2.5" : "gap-2.5"
                                )}
                            >
                                <Icon size={16} className={clsx("shrink-0", isActive ? "text-blue-600 dark:text-blue-400" : "opacity-70")} />
                                <span className={clsx("transition-all duration-300", isCollapsed ? "w-0 opacity-0 overflow-hidden" : "w-auto opacity-100")}>
                                    {link.name}
                                </span>
                            </Link>
                        );
                    })}
                </nav>

                <div className="px-2.5 pb-2">
                    <div className={clsx(
                        "bg-slate-50/70 dark:bg-[#0a0a0a] rounded-lg border border-slate-200 dark:border-white/5 transition-all duration-300 overflow-hidden",
                        isCollapsed ? "p-0 border-0 bg-transparent h-0 opacity-0 mb-0" : "p-2.5"
                    )}>
                        <div className="flex items-center justify-between mb-1.5">
                            <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Deception Node</span>
                            <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 font-bold">FYP</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="relative flex h-2 w-2 shrink-0">
                                <span className={clsx("animate-ping absolute inline-flex h-full w-full rounded-full opacity-75", exposureSyncing ? "bg-blue-400" : (sensorLive ? "bg-emerald-400" : "bg-amber-400"))}></span>
                                <span className={clsx("relative inline-flex rounded-full h-2 w-2", exposureSyncing ? "bg-blue-500" : (sensorLive ? "bg-emerald-500" : "bg-amber-500"))}></span>
                            </span>
                            <p className="text-[10.5px] font-medium text-slate-600 dark:text-slate-400 truncate">
                                {exposureSyncing
                                    ? "Exposure Syncing..."
                                    : statusPending
                                        ? "Checking Status..."
                                        : (sensorLive ? "Sensor Online" : "Sensor Offline")}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="p-2.5 border-t border-slate-200 dark:border-white/10 flex flex-col gap-2">
                    <div className={clsx("flex items-center transition-all", isCollapsed ? "justify-center flex-col gap-3" : "justify-between gap-1.5")}>
                        <button onClick={() => setShowSignOutConfirm(true)} className={clsx(
                            "flex items-center text-slate-500 dark:text-slate-400 hover:bg-red-500/10 hover:text-red-500 rounded-md transition-colors text-xs font-medium",
                            isCollapsed ? "p-2 justify-center" : "px-2.5 py-1.5 gap-2 flex-1"
                        )} title="Sign Out">
                            <LogOut size={16} />
                            <span className={clsx("transition-all duration-300", isCollapsed ? "w-0 opacity-0 overflow-hidden hidden" : "w-auto opacity-100")}>Sign Out</span>
                        </button>

                        <button
                            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                            className="p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-white/10 text-slate-500 dark:text-slate-400 transition-colors"
                            title={theme === "dark" ? "Light Mode" : "Dark Mode"}
                        >
                            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
                        </button>
                    </div>
                </div>
            </aside>
            <nav className="md:hidden fixed bottom-0 left-0 right-0 z-[90] bg-white dark:bg-[#0a0a0a] border-t border-slate-200 dark:border-white/10 flex items-center justify-around pb-safe overflow-hidden">
                {links.map((link) => {
                    const Icon = link.icon;
                    const isActive = pathname === link.href;
                    return (
                        <Link
                            key={link.href}
                            href={link.href}
                            className={clsx(
                                "flex flex-col items-center justify-center w-full py-2 gap-1 transition-colors",
                                isActive ? "text-blue-600 dark:text-blue-400" : "text-slate-500 hover:text-slate-900 dark:hover:text-slate-200"
                            )}
                        >
                            <Icon size={20} className={isActive ? "" : "opacity-70"} />
                            <span className="text-[10px] font-medium">{link.name}</span>
                        </Link>
                    );
                })}
            </nav>

            {showSignOutConfirm && (
                <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="bg-white dark:bg-[#0a0a0a] p-6 rounded-2xl border border-slate-200 dark:border-white/10 shadow-2xl max-w-sm w-full mx-4 animate-in zoom-in-95 duration-200">
                        <h3 className="text-lg font-bold mb-2">Sign Out</h3>
                        <p className="text-slate-500 dark:text-slate-400 text-sm mb-6">Are you sure you want to sign out of the dashboard?</p>
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => setShowSignOutConfirm(false)}
                                className="px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-100 dark:hover:bg-white/10 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={signOut}
                                className="px-4 py-2 rounded-lg bg-red-500 text-white text-sm font-bold shadow-lg shadow-red-500/20 hover:bg-red-600 transition-colors"
                            >
                                Confirm
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
