"use client";

import { useEffect, useState } from "react";

export default function LandingAnimations() {
  const [scrollProgress, setScrollProgress] = useState(0);

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

  return (
    <div 
      className="fixed top-0 left-0 h-[3px] bg-gradient-to-r from-blue-500 via-cyan-400 to-indigo-500 z-[9999] transition-all duration-75 shadow-[0_0_8px_rgba(59,130,246,0.5)]" 
      style={{ width: `${scrollProgress}%` }}
    />
  );
}
