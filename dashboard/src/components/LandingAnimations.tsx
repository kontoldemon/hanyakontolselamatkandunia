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

    // 2. Scroll Progress Tracker for scroll-driven animations
    const container = document.getElementById("snap-container");
    const handleScroll = () => {
      if (!container) return;
      const scrollTop = container.scrollTop;
      const docHeight = container.scrollHeight - container.clientHeight;
      if (docHeight > 0) {
        const progress = (scrollTop / docHeight) * 100;
        setScrollProgress(progress);

        // Map progress to active section (0 to 4)
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

  return (
    <>
      {/* Scroll Progress Bar */}
      <div 
        className="fixed top-0 left-0 h-[3px] bg-gradient-to-r from-blue-500 via-cyan-400 to-indigo-500 z-[9999] transition-all duration-75 shadow-[0_0_8px_rgba(59,130,246,0.5)]" 
        style={{ width: `${scrollProgress}%` }}
      />

      {/* Floating Active Defense Telemetry HUD Sidebar (Desktop Only) */}
      <div className="fixed right-6 top-[28%] z-40 hidden xl:flex flex-col gap-4 w-[240px] p-5 rounded-2xl border border-white/5 bg-[#0a0a0a]/60 backdrop-blur-xl animate-fade-in-scale select-none">
        
        {/* Radar Scanning Header */}
        <div className="flex items-center justify-between border-b border-white/5 pb-2.5">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-blue-400" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
            </span>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-300">Live Defense Telemetry</span>
          </div>
          <span className="text-[8px] font-mono text-slate-500">CS-NODE-01</span>
        </div>

        {/* Live Metrics Scanner */}
        <div className="space-y-4">
          <div className="flex flex-col gap-0.5">
            <span className="text-[8px] text-slate-500 uppercase tracking-widest font-bold">Active Module</span>
            <span className="text-xs font-mono font-bold text-white flex items-center gap-1.5">
              {sectionDetails[activeSection].icon}
              {sectionDetails[activeSection].title}
            </span>
          </div>

          <div className="flex flex-col gap-0.5">
            <span className="text-[8px] text-slate-500 uppercase tracking-widest font-bold">Module Status</span>
            <span className="text-[10px] font-bold font-mono text-emerald-400 flex items-center gap-1">
              <span className="w-1 h-1 rounded-full bg-emerald-400 animate-pulse" />
              {sectionDetails[activeSection].status}
            </span>
          </div>

          <div className="flex flex-col gap-0.5">
            <span className="text-[8px] text-slate-500 uppercase tracking-widest font-bold">Global Target</span>
            <span className="text-xs font-mono text-slate-300">Kuala Lumpur, MY (HQ)</span>
          </div>
        </div>

        {/* Active Section Step Indicators */}
        <div className="border-t border-white/5 pt-3 mt-1 space-y-1.5">
          {sectionDetails.map((sec, idx) => (
            <div key={idx} className="flex items-center justify-between text-[9px] font-mono">
              <span className={`${idx === activeSection ? "text-blue-400 font-bold" : "text-slate-500"}`}>
                {idx + 1}. {sec.title.split("-")[1]}
              </span>
              <span className={`w-1.5 h-1.5 rounded-full ${idx === activeSection ? "bg-blue-400 animate-pulse" : "bg-white/10"}`} />
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
