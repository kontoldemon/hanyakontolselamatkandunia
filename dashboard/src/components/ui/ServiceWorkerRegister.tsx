"use client";

import { useEffect, useSyncExternalStore } from "react";
import { WifiOff } from "lucide-react";

function subscribeToConnectivity(callback: () => void) {
  window.addEventListener("offline", callback);
  window.addEventListener("online", callback);
  return () => {
    window.removeEventListener("offline", callback);
    window.removeEventListener("online", callback);
  };
}

function getConnectivitySnapshot() {
  return typeof navigator === "undefined" ? false : !navigator.onLine;
}

export default function ServiceWorkerRegister() {
  const isOffline = useSyncExternalStore(
    subscribeToConnectivity,
    getConnectivitySnapshot,
    () => false,
  );

  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // Offline fallback is best-effort; normal dashboard should still load.
      });
    }
  }, []);

  if (!isOffline) return null;

  return (
    <aside
      aria-live="assertive"
      className="pointer-events-none fixed top-3 left-1/2 -translate-x-1/2 z-[150] flex items-center gap-2 rounded-full border border-rose-400/40 bg-rose-600 text-white px-3.5 py-1.5 shadow-[0_8px_24px_rgba(225,29,72,0.35),0_2px_8px_rgba(0,0,0,0.2)] animate-in fade-in slide-in-from-top-2 duration-200 select-none overflow-hidden"
    >
      {/* Specular highlight along top half */}
      <div className="absolute inset-0 rounded-full bg-gradient-to-b from-white/25 via-transparent to-transparent pointer-events-none" />

      <WifiOff size={13} className="text-white shrink-0 drop-shadow-sm" strokeWidth={2.4} />
      <span className="relative z-10 font-sans text-[11px] font-semibold text-white tracking-tight whitespace-nowrap">
        Offline mode
      </span>
    </aside>
  );
}
