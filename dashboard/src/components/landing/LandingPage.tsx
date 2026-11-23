"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { useTheme } from "next-themes";
import { ScrollProgressBar, ScrollToTopButton } from "./LandingPrimitives";
import LandingNavbar from "./LandingNavbar";
import CapabilitiesSection from "./CapabilitiesSection";
import {
  CtaSection,
  FaqSection,
  HeroSection,
  HowItWorksSection,
  LandingFooter,
} from "./LandingSections";

export default function LandingPage() {
  const { setTheme, resolvedTheme } = useTheme();
  const mounted = useSyncExternalStore(
    () => () => { },
    () => true,
    () => false,
  );

  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileMenuOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mobileMenuOpen]);

  const activeTheme = mounted ? (resolvedTheme === "light" ? "light" : "dark") : "dark";

  const handleToggleTheme = () => {
    const nextTheme = activeTheme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
  };

  return (
    <div className="min-h-screen bg-surface-bg font-sans text-text-primary antialiased selection:bg-blue-500/20 selection:text-text-primary">
      <ScrollProgressBar />
      <ScrollToTopButton />

      <LandingNavbar
        scrolled={scrolled}
        activeTheme={activeTheme}
        onToggleTheme={handleToggleTheme}
        mobileMenuOpen={mobileMenuOpen}
        onToggleMobileMenu={() => setMobileMenuOpen((prev) => !prev)}
        onCloseMobileMenu={() => setMobileMenuOpen(false)}
      />

      <main>
        <HeroSection />
        <CapabilitiesSection />
        <HowItWorksSection />
        <FaqSection
          openFaqIndex={openFaqIndex}
          onToggleFaq={(idx) => setOpenFaqIndex((prev) => (prev === idx ? null : idx))}
        />
        <CtaSection />
      </main>

      <LandingFooter />
    </div>
  );
}
