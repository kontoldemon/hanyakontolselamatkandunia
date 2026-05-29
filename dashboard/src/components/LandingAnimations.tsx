"use client";

import { useEffect } from "react";

export default function LandingAnimations() {
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("animate-fade-in-up");
            entry.target.classList.remove("opacity-0");
            // Stop observing once animated
            observer.unobserve(entry.target);
          }
        });
      },
      {
        threshold: 0.1,
        rootMargin: "0px 0px -50px 0px",
      }
    );

    const targets = document.querySelectorAll(".reveal-on-scroll");
    targets.forEach((target) => {
      target.classList.add("opacity-0", "transition-all");
      observer.observe(target);
    });

    return () => {
      targets.forEach((target) => observer.unobserve(target));
    };
  }, []);

  return null;
}
