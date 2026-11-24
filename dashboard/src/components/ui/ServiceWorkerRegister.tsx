"use client";

import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";

export default function ServiceWorkerRegister() {
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // Offline fallback is best-effort; normal dashboard should still load.
      });
    }

    const handleOffline = () => setIsOffline(true);
    const handleOnline = () => setIsOffline(false);

    if (typeof window !== "undefined") {
      setIsOffline(!navigator.onLine);
      window.addEventListener("offline", handleOffline);
      window.addEventListener("online", handleOnline);
    }

    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
    };
  }, []);

  if (!isOffline) return null;

  return (
    <aside
      aria-live="assertive"
      className="pointer-events-none fixed top-3 left-1/2 -translate-x-1/2 z-[150] flex items-center gap-2 rounded-full border border-amber-500/35 bg-gradient-to-r from-amber-500/15 via-black/65 to-amber-500/15 px-3.5 py-1.5 shadow-[0_8px_28px_rgba(0,0,0,0.45),0_0_18px_rgba(245,158,11,0.14),inset_0_1px_1px_rgba(255,255,255,0.2)] backdrop-blur-xl animate-in fade-in slide-in-from-top-2 duration-200 select-none overflow-hidden"
    >
      {/* Specular glass shine along top edge */}
      <div className="absolute inset-x-0 top-0 h-1/2 bg-gradient-to-b from-white/15 to-transparent pointer-events-none rounded-t-full" />

      <span className="relative flex h-1.5 w-1.5 shrink-0">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]" />
      </span>
      <WifiOff size={13} className="text-amber-400 shrink-0 drop-shadow-[0_0_6px_rgba(245,158,11,0.5)]" />
      <span className="relative z-10 font-sans text-[11px] font-semibold text-amber-100 tracking-tight whitespace-nowrap">
        Offline mode
      </span>
      <span className="relative z-10 text-amber-400/50 text-[10px]">&bull;</span>
      <span className="relative z-10 font-sans text-[11px] font-medium text-amber-200/85 tracking-tight whitespace-nowrap">
        Local cache active
      </span>
    </aside>
  );
}
