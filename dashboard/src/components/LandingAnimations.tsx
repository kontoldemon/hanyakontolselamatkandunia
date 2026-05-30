"use client";

import { useEffect, useState } from "react";
import { Shield, Activity, RefreshCw, Cpu, Server } from "lucide-react";

export default function LandingAnimations() {
  const [scrollProgress, setScrollProgress] = useState(0);
  const [activeSection, setActiveSection] = useState(0);

  useEffect(() => {
    // 1. Intersection Observer for scroll reveals
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("animate-fade-in-up");
            entry.target.classList.remove("opacity-0");
            observer.unobserve(entry.target);
          }
        });
      },
      {
        threshold: 0.05,
        rootMargin: "0px 0px -20px 0px",
      }
    );

    const targets = document.querySelectorAll(".reveal-on-scroll");
    targets.forEach((target) => {
      target.classList.add("opacity-0");
      observer.observe(target);
    });

    // 2. Scroll Progress Tracker for scroll-snapped modules
    const container = document.getElementById("snap-container");
    const handleScroll = () => {
      if (!container) return;
      const scrollTop = container.scrollTop;
      const docHeight = container.scrollHeight - container.clientHeight;
      if (docHeight > 0) {
        const progress = (scrollTop / docHeight) * 100;
        setScrollProgress(progress);

        const sectionIndex = Math.min(4, Math.floor(progress / 19.9));
        setActiveSection(sectionIndex);
      }
    };

    if (container) {
      container.addEventListener("scroll", handleScroll, { passive: true });
    }

    return () => {
      targets.forEach((target) => observer.unobserve(target));
      if (container) {
        container.removeEventListener("scroll", handleScroll);
      }
    };
  }, []);

  const sectionDetails = [
    { title: "CS-INTELLIGENCE", status: "SCANNING TRAFFIC", icon: <Activity size={12} className="text-blue-400" /> },
    { title: "CS-INGESTION", status: "PARSING SENSOR STREAM", icon: <RefreshCw size={12} className="text-cyan-400 animate-spin" /> },
    { title: "CS-ANALYSIS", status: "MITRE ATT&CK TTP CLASSIFY", icon: <Cpu size={12} className="text-purple-400" /> },
    { title: "CS-DATABASE", status: "HIGH-SPEED CLICKHOUSE READY", icon: <Server size={12} className="text-amber-400" /> },
    { title: "CS-SOAR", status: "ACTIVE DEFENSE SYSTEM ONLINE", icon: <Shield size={12} className="text-red-400" /> },
  ];

  // Helper to trigger snap scrolling to specific sections directly from hud clicks
  const scrollToSection = (idx: number) => {
    const container = document.getElementById("snap-container");
    if (container) {
      container.scrollTo({
        top: idx * window.innerHeight,
        behavior: "smooth"
      });
    }
  };

  return (
    <>
      {/* Scroll Progress Bar */}
      <div 
        className="fixed top-0 left-0 h-[3px] bg-gradient-to-r from-blue-500 via-cyan-400 to-indigo-500 z-[9999] transition-all duration-75 shadow-[0_0_8px_rgba(59,130,246,0.5)]" 
        style={{ width: `${scrollProgress}%` }}
      />

      {/* ── Sleek Interactive HUD Sidebar Nav (Desktop Only) ────────────────── */}
      <div className="fixed right-6 top-[30%] z-50 hidden xl:flex flex-row items-center gap-4">
        
        {/* Vertical Dot Navigation with radar pulses */}
        <div className="flex flex-col gap-4 py-3 px-2 rounded-full border border-white/5 bg-[#0a0a0c]/80 backdrop-blur-md">
          {sectionDetails.map((sec, idx) => (
            <button
              key={idx}
              onClick={() => {
                scrollToSection(idx);
              }}
              title={sec.title}
              className="relative flex items-center justify-center w-5 h-5 group cursor-pointer"
            >
              {/* Radar pulse for active item */}
              {idx === activeSection && (
                <span className="absolute inset-0 rounded-full border border-blue-500/50 animate-ping opacity-60 pointer-events-none" />
              )}
              {/* Hover label */}
              <span className="absolute right-7 px-2 py-0.5 rounded bg-[#0a0a0c] border border-white/10 text-[8px] text-slate-400 font-mono tracking-wider opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap">
                {sec.title.split("-")[1]}
              </span>
              
              {/* Outer ring */}
              <span className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center transition-all ${
                idx === activeSection ? "border-blue-500" : "border-white/10 group-hover:border-white/30"
              }`}>
                {/* Inner dot */}
                <span className={`w-1.5 h-1.5 rounded-full transition-all ${
                  idx === activeSection ? "bg-blue-400" : "bg-white/10 group-hover:bg-white/20"
                }`} />
              </span>
            </button>
          ))}
        </div>
      </div>
    </>
  );
}
