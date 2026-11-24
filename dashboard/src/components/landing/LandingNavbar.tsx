"use client";

import Image from "next/image";
import Link from "next/link";
import { Lock, Menu, Moon, Sun, X } from "lucide-react";
import { NAV_LINKS } from "./landingContent";
import { scrollToId } from "./LandingPrimitives";

interface LandingNavbarProps {
  scrolled: boolean;
  activeTheme: "light" | "dark";
  onToggleTheme: () => void;
  mobileMenuOpen: boolean;
  onToggleMobileMenu: () => void;
  onCloseMobileMenu: () => void;
}

export default function LandingNavbar({
  scrolled,
  activeTheme,
  onToggleTheme,
  mobileMenuOpen,
  onToggleMobileMenu,
  onCloseMobileMenu,
}: LandingNavbarProps) {
  return (
    <>
      <header
        className={`fixed inset-x-0 top-0 z-50 h-14 w-full transition-colors duration-200 ${scrolled
          ? "border-b border-border-line/10 bg-surface-bg/50 backdrop-blur-xl"
          : "border-b border-border-line/[0.04] bg-surface-bg/25 backdrop-blur-md"
          }`}
      >
        <div className="relative mx-auto flex h-full max-w-6xl items-center justify-between px-4 sm:px-6">
          {/* Left: Logo & Brand */}
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => scrollToId("top")}
              className="group flex items-center gap-2 py-1 text-left focus-visible:outline-none"
            >
              <Image
                src="/logo.svg"
                alt="CloudSentinel"
                width={20}
                height={20}
                className="h-5 w-5 transition-transform duration-200 group-hover:scale-105"
              />
              <span className="font-display text-[13px] font-bold tracking-tight text-text-primary sm:text-[14px]">
                Cloud<span className="text-blue-600 dark:text-blue-400">Sentinel</span>
              </span>
            </button>
          </div>

          {/* Center: Navigation Links - Absolutely Centered */}
          <div className="absolute left-1/2 -translate-x-1/2 hidden items-center gap-1 md:flex">
            {NAV_LINKS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => scrollToId(item.id)}
                className="whitespace-nowrap rounded-lg px-3 py-1.5 text-[12.5px] font-medium text-text-muted transition-colors hover:bg-border-line/[0.08] hover:text-text-primary focus-visible:outline-none"
              >
                {item.label}
              </button>
            ))}
          </div>

          {/* Right: Theme Toggle & War Room CTA */}
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={onToggleTheme}
              aria-label={activeTheme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border-line/10 bg-border-line/[0.04] text-text-muted transition hover:bg-border-line/[0.08] hover:text-text-primary focus-visible:outline-none active:scale-95"
            >
              <span
                key={activeTheme}
                className="inline-flex animate-[themeIconPop_0.35s_cubic-bezier(0.22,1,0.36,1)]"
              >
                {activeTheme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
              </span>
            </button>

            <Link
              href="/signin"
              className="hidden sm:inline-flex h-8 items-center justify-center gap-1.5 rounded-lg bg-blue-600 px-3.5 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-500 focus-visible:outline-none active:scale-95"
            >
              <Lock size={12} />
              <span>Enter War Room</span>
            </Link>

            <button
              type="button"
              onClick={onToggleMobileMenu}
              aria-label="Toggle navigation menu"
              aria-expanded={mobileMenuOpen}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border-line/10 bg-border-line/[0.04] text-text-muted transition hover:bg-border-line/[0.08] hover:text-text-primary md:hidden"
            >
              {mobileMenuOpen ? <X size={15} /> : <Menu size={15} />}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Menu Backdrop Scrim */}
      {mobileMenuOpen && (
        <div
          aria-hidden="true"
          onClick={onCloseMobileMenu}
          className="fixed inset-0 z-40 bg-black/10 md:hidden"
        />
      )}

      {/* Floating Glassy Mobile Menu Dropdown */}
      <div
        className={`fixed inset-x-3 top-16 z-50 overflow-hidden rounded-2xl border border-border-line/15 bg-surface-bg/50 backdrop-blur-2xl shadow-2xl shadow-black/10 transition-all duration-300 md:hidden ${
          mobileMenuOpen
            ? "pointer-events-auto opacity-100 translate-y-0"
            : "pointer-events-none opacity-0 -translate-y-2"
        }`}
      >
        <div className="flex flex-col gap-1 p-2.5">
          {NAV_LINKS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                onCloseMobileMenu();
                scrollToId(item.id);
              }}
              className="flex h-9 w-full items-center rounded-xl px-3 text-left text-xs font-medium text-text-muted transition hover:bg-border-line/10 hover:text-text-primary active:scale-[0.98]"
            >
              {item.label}
            </button>
          ))}
          <Link
            href="/signin"
            onClick={onCloseMobileMenu}
            className="mt-1.5 flex h-9 w-full items-center justify-center gap-1.5 rounded-xl bg-blue-600 px-3 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-500 active:scale-[0.98]"
          >
            <Lock size={13} />
            <span>Enter War Room</span>
          </Link>
        </div>
      </div>
    </>
  );
}
