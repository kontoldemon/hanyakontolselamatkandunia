"use client";

import { useState, useCallback, useEffect, useSyncExternalStore } from "react";
import Image from "next/image";
import Link from "next/link";
import { LayoutDashboard, Terminal, BrainCircuit, Settings, LogOut, ChevronLeft, PanelLeftOpen, Moon, Sun, X, Activity } from "lucide-react";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { useTheme } from "next-themes";
import { useAgentCommand } from "@/lib/AgentContext";

const SIDEBAR_COLLAPSED_KEY = "cloudsentinel.sidebar.collapsed";
const subscribeHydration = () => () => {};

export default function Sidebar() {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const mounted = useSyncExternalStore(subscribeHydration, () => true, () => false);
    const [showSignOutConfirm, setShowSignOutConfirm] = useState(false);
    const [isClosingSignOut, setIsClosingSignOut] = useState(false);
    const pathname = usePathname();
    const { theme, setTheme } = useTheme();

    useEffect(() => {
        if (typeof window === "undefined") return;
        // eslint-disable-next-line react-hooks/set-state-in-effect -- restore the persisted sidebar state after hydration
        setIsCollapsed(window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1");
    }, []);

    const closeSignOutModal = useCallback(() => {
        if (isClosingSignOut) return;
        setIsClosingSignOut(true);
        setTimeout(() => {
            setShowSignOutConfirm(false);
            setIsClosingSignOut(false);
        }, 180);
    }, [isClosingSignOut]);

    useEffect(() => {
        if (!showSignOutConfirm) return;
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") closeSignOutModal();
        };
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [showSignOutConfirm, closeSignOutModal]);

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
        { name: "Telemetry", href: "/telemetry", icon: Activity },
        { name: "Settings", href: "/settings", icon: Settings },
    ];

    async function signOut() {
        await fetch("/api/auth/logout", { method: "POST" });
        window.location.assign("/signin");
    }

    return (
        <>
            <aside
                className={clsx(
                    "hidden md:flex flex-col bg-white/70 dark:bg-[#050505]/90 border-r border-slate-200 dark:border-white/10 transition-[width] duration-200 ease-in-out backdrop-blur-md h-dvh sticky top-0 will-change-[width] z-30",
                    isCollapsed ? "w-16" : "w-52"
                )}
            >
                <div
                    className={clsx(
                        "h-14 border-b border-slate-200 dark:border-white/10 flex items-center overflow-hidden transition-[padding] duration-200",
                        isCollapsed ? "justify-center px-0" : "justify-between px-2.5"
                    )}
                >
                    <div
                        className={clsx(
                            "flex items-center overflow-hidden transition-[max-width,opacity] duration-200 ease-in-out min-w-0",
                            isCollapsed ? "max-w-0 opacity-0 pointer-events-none hidden" : "max-w-40 opacity-100 flex-1"
                        )}
                    >
                        <Link href="/dashboard" className="group flex items-center pl-2.5 pr-1 text-left focus-visible:outline-none whitespace-nowrap">
                            <div className="flex h-5 w-5 shrink-0 items-center justify-center">
                                <Image
                                    src="/logo.svg"
                                    alt="CloudSentinel"
                                    width={18}
                                    height={18}
                                    className="h-[18px] w-[18px] shrink-0 transition-transform duration-200 group-hover:scale-105"
                                />
                            </div>
                            <span className="font-display text-sm font-bold tracking-tight text-slate-900 dark:text-white whitespace-nowrap leading-none ml-2">
                                Cloud<span className="text-blue-600 dark:text-blue-400">Sentinel</span>
                            </span>
                        </Link>
                    </div>

                    <button
                        onClick={() => setIsCollapsed(!isCollapsed)}
                        className={clsx(
                            "group/expand relative flex shrink-0 items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 text-slate-500 dark:text-slate-400 transition-colors cursor-pointer",
                            isCollapsed ? "h-9 w-9" : "h-7 w-7"
                        )}
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
                                    size={20}
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
                                    "flex items-center h-9 rounded-lg text-xs font-medium transition-colors duration-150 whitespace-nowrap",
                                    isCollapsed ? "justify-center px-0" : "px-2.5",
                                    isActive
                                        ? "bg-blue-50 text-blue-600 dark:bg-white/5 dark:text-blue-400 font-semibold"
                                        : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-slate-200"
                                )}
                            >
                                <div className="flex h-5 w-5 shrink-0 items-center justify-center">
                                    <Icon size={17} className={clsx("shrink-0", isActive ? "text-blue-600 dark:text-blue-400" : "opacity-70")} />
                                </div>
                                <span
                                    className={clsx(
                                        "overflow-hidden whitespace-nowrap transition-[max-width,opacity] duration-200 ease-in-out ml-2",
                                        isCollapsed ? "max-w-0 opacity-0 pointer-events-none hidden" : "max-w-36 opacity-100"
                                    )}
                                >
                                    {link.name}
                                </span>
                            </Link>
                        );
                    })}
                </nav>

                <div className="p-2.5 border-t border-slate-200 dark:border-white/10 flex flex-col gap-1.5">
                    <button
                        type="button"
                        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                        className={clsx(
                            "flex items-center h-9 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-slate-200 transition-colors duration-150 text-xs font-medium whitespace-nowrap cursor-pointer",
                            isCollapsed ? "justify-center px-0" : "px-2.5"
                        )}
                        title={mounted ? (theme === "dark" ? "Light Mode" : "Dark Mode") : "Theme"}
                    >
                        <div className="flex h-5 w-5 shrink-0 items-center justify-center">
                            {mounted ? (theme === "dark" ? <Sun size={17} /> : <Moon size={17} />) : <Moon size={17} />}
                        </div>
                        <span
                            className={clsx(
                                "overflow-hidden whitespace-nowrap transition-[max-width,opacity] duration-200 ease-in-out ml-2",
                                isCollapsed ? "max-w-0 opacity-0 pointer-events-none hidden" : "max-w-36 opacity-100"
                            )}
                        >
                            {mounted ? (theme === "dark" ? "Light Mode" : "Dark Mode") : "Theme"}
                        </span>
                    </button>

                    <button
                        type="button"
                        onClick={() => setShowSignOutConfirm(true)}
                        className={clsx(
                            "flex items-center h-9 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-rose-500/10 hover:text-rose-500 transition-colors duration-150 text-xs font-medium whitespace-nowrap cursor-pointer",
                            isCollapsed ? "justify-center px-0" : "px-2.5"
                        )}
                        title="Sign Out"
                    >
                        <div className="flex h-5 w-5 shrink-0 items-center justify-center">
                            <LogOut size={17} />
                        </div>
                        <span
                            className={clsx(
                                "overflow-hidden whitespace-nowrap transition-[max-width,opacity] duration-200 ease-in-out ml-2",
                                isCollapsed ? "max-w-0 opacity-0 pointer-events-none hidden" : "max-w-36 opacity-100"
                            )}
                        >
                            Sign Out
                        </span>
                    </button>
                </div>
            </aside>

            {/* Mobile Top Header (md:hidden) */}
            <header className="md:hidden shrink-0 h-13 px-4 bg-white/90 dark:bg-[#050505]/95 border-b border-slate-200 dark:border-white/10 backdrop-blur-md flex items-center justify-between z-30">
                <Link href="/dashboard" className="flex items-center gap-2 min-w-0">
                    <Image
                        src="/logo.svg"
                        alt="CloudSentinel"
                        width={20}
                        height={20}
                        className="h-5 w-5 shrink-0"
                    />
                    <span className="font-display text-sm font-bold tracking-tight text-slate-900 dark:text-white truncate">
                        Cloud<span className="text-blue-600 dark:text-blue-400">Sentinel</span>
                    </span>
                </Link>
                <div className="flex items-center gap-1">
                    <button
                        type="button"
                        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                        className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/10 transition-colors cursor-pointer"
                        aria-label={mounted ? (theme === "dark" ? "Light Mode" : "Dark Mode") : "Theme"}
                    >
                        {mounted ? (theme === "dark" ? <Sun size={18} /> : <Moon size={18} />) : <Moon size={18} />}
                    </button>
                    <button
                        type="button"
                        onClick={() => setShowSignOutConfirm(true)}
                        className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 dark:text-slate-400 hover:bg-rose-500/10 hover:text-rose-500 transition-colors cursor-pointer"
                        aria-label="Sign Out"
                    >
                        <LogOut size={18} />
                    </button>
                </div>
            </header>

            <nav className="md:hidden fixed bottom-0 left-0 right-0 z-[90] bg-white/95 dark:bg-[#0a0a0a]/95 backdrop-blur-md border-t border-slate-200 dark:border-white/10 flex items-center justify-around pb-safe overflow-hidden">
                {links.map((link) => {
                    const Icon = link.icon;
                    const isActive = pathname === link.href;
                    return (
                        <Link
                            key={link.href}
                            href={link.href}
                            className={clsx(
                                "flex flex-col items-center justify-center w-full min-h-[56px] py-2 px-1 gap-1 transition-colors min-w-0",
                                isActive ? "text-blue-600 dark:text-blue-400" : "text-slate-500 hover:text-slate-900 dark:hover:text-slate-200"
                            )}
                        >
                            <Icon size={20} className={isActive ? "" : "opacity-70"} />
                            <span className="text-[10px] font-medium truncate max-w-full">{link.name}</span>
                        </Link>
                    );
                })}
            </nav>

            {showSignOutConfirm && (
                <div
                    onClick={closeSignOutModal}
                    className={clsx(
                        "fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-md p-4",
                        isClosingSignOut ? "animate-overlay-out" : "animate-overlay-in"
                    )}
                >
                    <div
                        onClick={(e) => e.stopPropagation()}
                        className={clsx(
                            "relative max-w-[320px] w-full overflow-hidden rounded-3xl border border-slate-200/80 bg-white/95 p-6 text-center shadow-2xl backdrop-blur-2xl dark:border-white/10 dark:bg-[#0c0c0e] dark:shadow-[0_24px_60px_rgba(0,0,0,0.8)]",
                            isClosingSignOut ? "animate-modal-out" : "animate-modal-in"
                        )}
                    >
                        {/* Dismiss Button */}
                        <button
                            type="button"
                            onClick={closeSignOutModal}
                            className="absolute top-4 right-4 flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition cursor-pointer"
                            aria-label="Close"
                        >
                            <X size={15} />
                        </button>

                        {/* Icon Header */}
                        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200/80 bg-slate-100/80 text-slate-700 shadow-sm dark:border-white/10 dark:bg-white/[0.05] dark:text-slate-200">
                            <LogOut size={16} className="translate-x-0.5 text-rose-500 dark:text-rose-400" />
                        </div>

                        {/* Title & Description */}
                        <h3 className="font-display text-base font-bold tracking-tight text-slate-900 sm:text-lg dark:text-white">
                            Sign Out
                        </h3>
                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                            You will need to sign in again to access the War Room.
                        </p>

                        {/* Action Buttons */}
                        <div className="mt-5 flex items-center gap-2.5">
                            <button
                                type="button"
                                onClick={closeSignOutModal}
                                className="inline-flex h-11 flex-1 items-center justify-center rounded-full border border-slate-200/80 bg-white/80 dark:border-white/10 dark:bg-white/[0.04] text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.08] transition active:scale-95 cursor-pointer"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={signOut}
                                className="inline-flex h-11 flex-1 items-center justify-center gap-1.5 rounded-full bg-rose-600 hover:bg-rose-500 px-4 text-xs font-semibold text-white shadow-sm transition active:scale-95 cursor-pointer"
                            >
                                <LogOut size={12} />
                                <span>Sign Out</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
