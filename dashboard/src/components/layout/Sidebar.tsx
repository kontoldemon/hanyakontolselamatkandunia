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
                    isCollapsed ? "w-20" : "w-64"
                )}
            >
                <div className="h-14 px-4 border-b border-slate-200 dark:border-white/10 flex items-center justify-between">
                    <div className={clsx("flex items-center gap-2.5 overflow-hidden transition-all", isCollapsed ? "w-0 opacity-0" : "w-auto opacity-100")}>
                        <Link href="/dashboard" className="group flex items-center gap-2 text-left focus-visible:outline-none">
                            <Image
                                src="/logo.svg"
                                alt="CloudSentinel"
                                width={20}
                                height={20}
                                className="h-5 w-5 shrink-0 transition-transform duration-200 group-hover:scale-105"
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
                                    width={20}
                                    height={20}
                                    className="h-5 w-5 transition-all duration-200 group-hover/expand:opacity-0 group-hover/expand:scale-75"
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

                <nav className="flex-1 p-3 space-y-1 overflow-y-auto overflow-x-hidden">
                    {links.map((link) => {
                        const Icon = link.icon;
                        const isActive = pathname === link.href;

                        return (
                            <Link
                                key={link.href}
                                href={link.href}
                                title={isCollapsed ? link.name : ""}
                                className={clsx(
                                    "flex items-center px-3 py-2 rounded-lg transition-all text-xs font-medium whitespace-nowrap",
                                    isActive
                                        ? "bg-blue-50 text-blue-600 dark:bg-white/5 dark:text-blue-400"
                                        : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-slate-200",
                                    isCollapsed ? "justify-center" : "gap-2.5"
                                )}
                            >
                                <Icon size={17} className={clsx("shrink-0", isActive ? "text-blue-600 dark:text-blue-400" : "opacity-70")} />
                                <span className={clsx("transition-all duration-300", isCollapsed ? "w-0 opacity-0 overflow-hidden" : "w-auto opacity-100")}>
                                    {link.name}
                                </span>
                            </Link>
                        );
                    })}
                </nav>

                <div className="px-3 pb-3">
                    <div className={clsx(
                        "bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-500 rounded-xl transition-all duration-300 overflow-hidden flex flex-col items-center justify-center text-center",
                        isCollapsed ? "p-0 h-0 opacity-0 border-0 mb-0" : "p-3 mb-1"
                    )}>
                        <span className="text-[10px] font-bold uppercase tracking-wider mb-1">FYP Prototype</span>
                        <span className="text-[9px] leading-tight opacity-80">Live API bridge enabled.<br/>Sensor status below.</span>
                    </div>
                </div>

                <div className="px-3 pb-3">
                    <div className={clsx(
                        "bg-slate-50 dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 transition-all duration-300 overflow-hidden",
                        isCollapsed ? "p-0 border-0 bg-transparent h-0 opacity-0" : "p-4 mb-3"
                    )}>
                        <p className="text-xs text-slate-500 dark:text-slate-400 font-medium mb-2 whitespace-nowrap">System Status</p>
                        <div className="flex items-center gap-2 mb-2">
                            <span className="relative flex h-2 w-2">
                                <span className={clsx("animate-ping absolute inline-flex h-full w-full rounded-full opacity-75", exposureSyncing ? "bg-blue-400" : (sensorLive ? "bg-green-400" : "bg-amber-400"))}></span>
                                <span className={clsx("relative inline-flex rounded-full h-2 w-2", exposureSyncing ? "bg-blue-500" : (sensorLive ? "bg-green-500" : "bg-amber-500"))}></span>
                            </span>
                            <p className="text-[10px] text-slate-400 dark:text-slate-500 whitespace-nowrap">
                                {exposureSyncing
                                    ? "Exposure Changing..."
                                    : statusPending
                                        ? "Checking Sensor Status..."
                                        : (sensorLive ? "Sensor Node Online" : "Sensor API Offline")}
                            </p>
                        </div>
                        {exposureSyncing && (
                            <div className="text-[10px] px-2 py-1 rounded border border-blue-500/20 bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold">
                                Node state updating now
                            </div>
                        )}
                    </div>
                </div>

                <div className="p-4 border-t border-slate-200 dark:border-white/10 flex flex-col gap-2">
                    <div className={clsx("flex items-center transition-all", isCollapsed ? "justify-center flex-col gap-4" : "justify-between gap-2")}>
                        <button onClick={() => setShowSignOutConfirm(true)} className={clsx(
                            "flex items-center text-slate-500 dark:text-slate-400 hover:bg-red-500/10 hover:text-red-500 rounded-md transition-colors text-xs font-medium",
                            isCollapsed ? "p-2 justify-center" : "px-3 py-2 gap-2 flex-1"
                        )} title="Sign Out">
                            <LogOut size={18} />
                            <span className={clsx("transition-all duration-300", isCollapsed ? "w-0 opacity-0 overflow-hidden hidden" : "w-auto opacity-100")}>Sign Out</span>
                        </button>

                        <button
                            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                            className={clsx("p-2 rounded-md hover:bg-slate-100 dark:hover:bg-white/10 text-slate-500 dark:text-slate-400 transition-colors", isCollapsed ? "" : "origin-right")}
                        >
                            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
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
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
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
